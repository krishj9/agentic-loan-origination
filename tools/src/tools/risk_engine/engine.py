"""Deterministic mock risk engine — ``risk_engine.evaluate`` (P4-T3/T4).

Design §7 / Requirements §5.3

Guarantees
----------
* **Deterministic**: identical inputs → identical outputs across any number of runs
  (same process, different process, different machine).
* **Pure function**: no side effects, no I/O, no randomness.
* **Config-driven**: band thresholds and score ranges are read from
  ``tools/config/risk_policy.yaml`` — changing that file changes behaviour
  without touching code, enabling the evaluation harness to verify drift (P6-T6).
* **Transparent**: every intermediate value (income_band, utilization_band,
  score_range rationale) is included in the output for downstream use in
  decision rationale (design §7.7).

Scoring algorithm (design §7.4)
--------------------------------
1. If ``request.risk_profile`` override is set → use it, skip classification.
2. Classify PRIME: income > 80,000 AND utilization < 30%.
3. Classify SUBPRIME: income < 40,000 OR utilization > 60%.
4. Everything else → NEAR_PRIME.
5. Credit score = deterministic value within the band's configured range,
   derived from ``applicant_id`` via MD5 offset (no randomness).
6. Tradelines generated deterministically from seed = ``applicant_id``.
7. Flags raised from thresholds in the policy config.
"""

import hashlib
from decimal import Decimal
from typing import Any

from shared.schemas import AccountType, RiskFlag, RiskProfile, RiskRequest, RiskResponse, Tradeline
from tools.log import get_logger
from tools.risk_engine.config import RiskPolicyConfig, get_policy

log = get_logger("risk_engine")


# ── Band classification ──────────────────────────────────────────────────────

def _classify_profile(
    annual_income: Decimal,
    debt_utilization: Decimal,
    policy: RiskPolicyConfig,
) -> RiskProfile:
    """Apply policy band rules and return the appropriate :class:`RiskProfile`.

    Classification order (design §7.4):
      1. PRIME: income > threshold AND utilization < threshold.
      2. SUBPRIME: income < threshold OR utilization > threshold.
      3. NEAR_PRIME: everything else.

    Args:
        annual_income: Annualised gross income in USD.
        debt_utilization: Aggregate debt utilisation ratio (0.0–1.0).
        policy: Loaded risk policy configuration.

    Returns:
        The matching :class:`RiskProfile`.
    """
    prime = policy.bands.get("PRIME")
    subprime = policy.bands.get("SUBPRIME")

    is_prime = (
        prime is not None
        and prime.income_min_exclusive is not None
        and prime.utilization_max_exclusive is not None
        and annual_income > prime.income_min_exclusive
        and debt_utilization < prime.utilization_max_exclusive
    )
    if is_prime:
        return RiskProfile.PRIME

    is_subprime = subprime is not None and (
        (subprime.income_max_exclusive is not None and annual_income < subprime.income_max_exclusive)
        or (
            subprime.utilization_min_exclusive is not None
            and debt_utilization > subprime.utilization_min_exclusive
        )
    )
    if is_subprime:
        return RiskProfile.SUBPRIME

    return RiskProfile.NEAR_PRIME


# ── Deterministic scoring ────────────────────────────────────────────────────

def _deterministic_score(profile: RiskProfile, seed: str, policy: RiskPolicyConfig) -> int:
    """Return a deterministic credit score within the band's configured range.

    Uses an MD5 hash of the seed string to generate a stable offset within
    [score_range.min, score_range.max).  MD5 is used here purely for its
    deterministic mapping property — not for security.

    Args:
        profile: The assigned risk profile.
        seed: Stable seed string (e.g. ``applicant_id``).
        policy: Loaded risk policy configuration.

    Returns:
        Integer credit score within the band range.
    """
    band = policy.bands.get(profile.value)
    if band is None:
        return 600  # safe fallback
    lo = band.score_range.min
    hi = band.score_range.max
    offset = int(hashlib.md5(f"{seed}:score".encode()).hexdigest()[:8], 16)
    return lo + (offset % (hi - lo))


# ── Tradeline synthesis ──────────────────────────────────────────────────────

_ACCOUNT_TYPE_MAP: dict[str, AccountType] = {
    "CREDIT_CARD": AccountType.CREDIT_CARD,
    "AUTO_LOAN": AccountType.AUTO_LOAN,
    "MORTGAGE": AccountType.MORTGAGE,
}


def _synthesize_tradelines(seed: str, policy: RiskPolicyConfig) -> list[Tradeline]:
    """Generate 1–5 deterministic synthetic tradelines from ``seed``.

    Design §7.6: tradeline count and attributes are derived from the seed
    so the same applicant always produces the same tradelines.

    Args:
        seed: Stable seed string (e.g. ``applicant_id``).
        policy: Loaded risk policy configuration.

    Returns:
        List of :class:`Tradeline` objects.
    """
    tl_cfg = policy.tradelines
    account_types = [_ACCOUNT_TYPE_MAP.get(t, AccountType.CREDIT_CARD) for t in tl_cfg.account_types]

    count_hash = int(hashlib.md5(f"{seed}:count".encode()).hexdigest()[0], 16)
    span = tl_cfg.max_count - tl_cfg.min_count
    n_tradelines = tl_cfg.min_count + (count_hash % (span + 1))

    tradelines: list[Tradeline] = []
    for i in range(n_tradelines):
        h = int(hashlib.md5(f"{seed}:tradeline:{i}".encode()).hexdigest()[:8], 16)
        account_type = account_types[h % len(account_types)]
        limit = Decimal(str(tl_cfg.balance_base + (h % tl_cfg.balance_variance)))
        raw_util = tl_cfg.utilization_base + (h % tl_cfg.utilization_variance_pct) / 100.0
        utilization = Decimal(str(round(min(raw_util, 1.0), 2)))
        balance = (limit * utilization).quantize(Decimal("0.01"))
        tradelines.append(
            Tradeline(account_type=account_type, balance=balance, limit=limit, utilization=utilization)
        )
    return tradelines


# ── Flag derivation ──────────────────────────────────────────────────────────

def _derive_flags(
    annual_income: Decimal,
    debt_utilization: Decimal,
    policy: RiskPolicyConfig,
) -> list[RiskFlag]:
    """Derive risk flags from the input values using policy thresholds.

    Args:
        annual_income: Annualised gross income in USD.
        debt_utilization: Aggregate debt utilisation ratio.
        policy: Loaded risk policy configuration.

    Returns:
        List of triggered :class:`RiskFlag` values.
    """
    flags_cfg = policy.flags
    flags: list[RiskFlag] = []

    high_util_threshold = Decimal(str(flags_cfg.get("HIGH_UTILIZATION", {}).get("threshold", 0.60)))
    mod_util_min = Decimal(str(flags_cfg.get("MODERATE_UTILIZATION", {}).get("threshold_min", 0.30)))
    low_income_max = Decimal(str(flags_cfg.get("LOW_INCOME", {}).get("threshold_max", 40000.0)))
    near_prime_min = Decimal(str(flags_cfg.get("NEAR_PRIME_INCOME", {}).get("threshold_min", 40000.0)))
    near_prime_max = Decimal(str(flags_cfg.get("NEAR_PRIME_INCOME", {}).get("threshold_max", 80000.0)))

    if debt_utilization > high_util_threshold:
        flags.append(RiskFlag.HIGH_UTILIZATION)
    elif debt_utilization >= mod_util_min:
        flags.append(RiskFlag.MODERATE_UTILIZATION)

    if annual_income < low_income_max:
        flags.append(RiskFlag.LOW_INCOME)
    elif near_prime_min <= annual_income <= near_prime_max:
        flags.append(RiskFlag.NEAR_PRIME_INCOME)

    return flags


# ── Explainability labels ────────────────────────────────────────────────────

def _income_band_label(annual_income: Decimal) -> str:
    """Return a human-readable income band label for explainability."""
    if annual_income > Decimal("80000"):
        return "HIGH"
    if annual_income >= Decimal("40000"):
        return "MID"
    return "LOW"


def _utilization_band_label(debt_utilization: Decimal) -> str:
    """Return a human-readable utilisation band label for explainability."""
    if debt_utilization < Decimal("0.30"):
        return "LOW"
    if debt_utilization <= Decimal("0.60"):
        return "MODERATE"
    return "HIGH"


def _build_rationale(
    profile: RiskProfile,
    credit_score: int,
    income_band: str,
    util_band: str,
    annual_income: Decimal,
    debt_utilization: Decimal,
    policy: RiskPolicyConfig,
) -> str:
    """Compose a human-readable score-range rationale string (design §7.7).

    The rationale references only the rule-based intermediate values so
    the decision node can produce human-readable justification without
    inventing unsupported explanations.

    Args:
        profile: Assigned risk profile.
        credit_score: Deterministic credit score.
        income_band: Human-readable income label.
        util_band: Human-readable utilisation label.
        annual_income: Raw annual income value.
        debt_utilization: Raw utilisation ratio.
        policy: Loaded policy for band description.

    Returns:
        One-sentence rationale string.
    """
    band_cfg = policy.bands.get(profile.value)
    score_min = band_cfg.score_range.min if band_cfg else 0
    score_max = band_cfg.score_range.max if band_cfg else 999
    return (
        f"Annual income {income_band} (${annual_income:,.0f}), "
        f"debt utilisation {util_band} ({float(debt_utilization):.0%}). "
        f"Assigned {profile.value} band (score range {score_min}–{score_max}). "
        f"Deterministic credit score: {credit_score}."
    )


# ── Public entry point ───────────────────────────────────────────────────────

def evaluate(request: RiskRequest) -> RiskResponse:
    """Evaluate the deterministic mock risk engine for one applicant (P4-T3).

    This function is a **pure, deterministic** function with no side effects.
    The only I/O allowed by this module is the structured log emit.

    Algorithm:
      1. Apply ``risk_profile`` override if present, otherwise classify.
      2. Generate deterministic credit score from seed + band config.
      3. Synthesize tradelines from seed.
      4. Derive risk flags from input thresholds.
      5. Build explainability labels and rationale.

    Args:
        request: Validated :class:`~shared.schemas.RiskRequest`.

    Returns:
        :class:`~shared.schemas.RiskResponse` with full explainability fields.
    """
    policy = get_policy()
    ctx: dict[str, Any] = {"application_id": request.applicant_id}

    profile = request.risk_profile or _classify_profile(
        request.annual_income, request.debt_utilization, policy
    )

    credit_score = _deterministic_score(profile, request.applicant_id, policy)
    tradelines = _synthesize_tradelines(request.applicant_id, policy)
    flags = _derive_flags(request.annual_income, request.debt_utilization, policy)

    income_band = _income_band_label(request.annual_income)
    util_band = _utilization_band_label(request.debt_utilization)
    rationale = _build_rationale(
        profile, credit_score, income_band, util_band,
        request.annual_income, request.debt_utilization, policy,
    )

    log.info(
        "risk evaluation complete",
        correlation=ctx,
        risk_profile=profile.value,
        credit_score=credit_score,
        income_band=income_band,
        utilization_band=util_band,
        flag_count=len(flags),
        tradeline_count=len(tradelines),
    )

    return RiskResponse(
        applicant_id=request.applicant_id,
        risk_profile=profile,
        credit_score=credit_score,
        tradelines=tradelines,
        risk_flags=flags,
        income_band=income_band,
        utilization_band=util_band,
        score_range_rationale=rationale,
    )
