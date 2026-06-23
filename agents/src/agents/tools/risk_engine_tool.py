"""Risk-engine tool interface — ``risk_engine.evaluate`` (P3-T10).

Defines the Pydantic v2 request/response wrappers and the callable invoked
by the risk subgraph.  Delegates to the Phase 4 deterministic engine
(``agents.tools.risk_engine``) when available; falls back to a deterministic
stub that satisfies the same contract so end-to-end graph tests pass offline.

The stub applies the same income/utilisation band rules described in
design §7.4 so golden-case profiles remain consistent.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas import (
    AccountType,
    RiskFlag,
    RiskProfile,
    RiskRequest,
    RiskResponse,
    Tradeline,
)

# ── Request / Response wrappers (thin aliases for Gateway schema alignment) ──

class RiskEngineRequest(BaseModel):
    """Gateway-facing input contract for ``risk_engine.evaluate``."""

    model_config = ConfigDict(populate_by_name=True)

    applicant_id: str = Field(description="Application/applicant identifier.")
    annual_income: Decimal = Field(description="Annualised gross income (USD).")
    debt_utilization: Decimal = Field(description="Aggregate debt utilisation ratio (0.0–1.0).")
    risk_profile: RiskProfile | None = Field(
        default=None,
        description="Optional override for golden-case replay tests.",
    )

    def to_risk_request(self) -> RiskRequest:
        """Convert to the canonical shared.schemas RiskRequest."""
        return RiskRequest(
            applicant_id=self.applicant_id,
            annual_income=self.annual_income,
            debt_utilization=self.debt_utilization,
            risk_profile=self.risk_profile,
        )


class RiskEngineResponse(BaseModel):
    """Gateway-facing output contract for ``risk_engine.evaluate``.

    Wraps ``shared.schemas.RiskResponse`` with an explicit model so the
    Gateway schema introspection sees a concrete Pydantic model.
    """

    model_config = ConfigDict(populate_by_name=True)

    risk_response: RiskResponse = Field(description="Full risk engine response.")


# ── Stub implementation ─────────────────────────────────────────────────────

def _classify_profile(annual_income: Decimal, debt_utilization: Decimal) -> RiskProfile:
    """Apply design §7.4 band rules to determine the risk profile."""
    if annual_income > Decimal("80000") and debt_utilization < Decimal("0.30"):
        return RiskProfile.PRIME
    if annual_income < Decimal("40000") or debt_utilization > Decimal("0.60"):
        return RiskProfile.SUBPRIME
    return RiskProfile.NEAR_PRIME


def _stub_score(profile: RiskProfile, seed: str) -> int:
    """Return a deterministic credit score within the profile's band."""
    offset = int(hashlib.md5(seed.encode()).hexdigest()[:4], 16)
    ranges = {
        RiskProfile.PRIME: (720, 800),
        RiskProfile.NEAR_PRIME: (620, 700),
        RiskProfile.SUBPRIME: (500, 600),
    }
    lo, hi = ranges[profile]
    return lo + (offset % (hi - lo))


_ACCOUNT_TYPES = [AccountType.CREDIT_CARD, AccountType.AUTO_LOAN, AccountType.MORTGAGE]


def _stub_tradelines(seed: str, n: int) -> list[Tradeline]:
    """Generate ``n`` deterministic synthetic tradelines from the seed."""
    lines = []
    for i in range(n):
        h = int(hashlib.md5(f"{seed}:{i}".encode()).hexdigest()[:8], 16)
        account_type = _ACCOUNT_TYPES[h % len(_ACCOUNT_TYPES)]
        limit = Decimal(str(5000 + (h % 45000)))
        utilization = Decimal(str(round(0.1 + (h % 60) / 100.0, 2)))
        balance = (limit * utilization).quantize(Decimal("0.01"))
        lines.append(Tradeline(account_type=account_type, balance=balance, limit=limit, utilization=utilization))
    return lines


def _stub_evaluate(request: RiskEngineRequest) -> RiskResponse:
    """Deterministic stub evaluation applying design §7.4 rules."""
    profile = request.risk_profile or _classify_profile(request.annual_income, request.debt_utilization)
    seed = request.applicant_id
    score = _stub_score(profile, seed)

    n_tradelines = 1 + int(hashlib.md5(seed.encode()).hexdigest()[0], 16) % 4
    tradelines = _stub_tradelines(seed, n_tradelines)

    flags: list[RiskFlag] = []
    if request.debt_utilization > Decimal("0.60"):
        flags.append(RiskFlag.HIGH_UTILIZATION)
    elif request.debt_utilization > Decimal("0.30"):
        flags.append(RiskFlag.MODERATE_UTILIZATION)
    if request.annual_income < Decimal("40000"):
        flags.append(RiskFlag.LOW_INCOME)
    elif request.annual_income < Decimal("80000"):
        flags.append(RiskFlag.NEAR_PRIME_INCOME)

    income_band = (
        "HIGH" if request.annual_income > Decimal("80000")
        else "MID" if request.annual_income >= Decimal("40000")
        else "LOW"
    )
    util_band = (
        "LOW" if request.debt_utilization < Decimal("0.30")
        else "MODERATE" if request.debt_utilization <= Decimal("0.60")
        else "HIGH"
    )
    rationale = (
        f"Annual income {income_band} (${request.annual_income:,.0f}), "
        f"utilization {util_band} ({float(request.debt_utilization):.0%}). "
        f"Assigned {profile} — score band {score}."
    )
    return RiskResponse(
        applicant_id=request.applicant_id,
        risk_profile=profile,
        credit_score=score,
        tradelines=tradelines,
        risk_flags=flags,
        income_band=income_band,
        utilization_band=util_band,
        score_range_rationale=rationale,
    )


def call_risk_engine(request: RiskEngineRequest) -> RiskResponse:
    """Invoke the deterministic mock risk engine.

    Delegates to the Phase 4 engine (``tools.risk_engine.evaluate``)
    when available; uses the local stub otherwise.

    Args:
        request: Validated ``RiskEngineRequest``.

    Returns:
        ``RiskResponse`` from shared.schemas with full explainability fields.
    """
    try:
        from tools.risk_engine import evaluate  # Phase 4

        return evaluate(request.to_risk_request())
    except ImportError:
        return _stub_evaluate(request)


def get_tool_spec() -> dict[str, Any] | None:
    """Return the Gateway tool specification for this tool."""
    from agents.tools.schemas import RISK_ENGINE_TOOL_SPEC

    return RISK_ENGINE_TOOL_SPEC
