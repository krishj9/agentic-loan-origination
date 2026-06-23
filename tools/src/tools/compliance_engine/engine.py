"""Rule-based compliance engine — ``compliance_engine.evaluate`` (P4-T5).

Design §8 / Requirements §5.4

Guarantees
----------
* **Deterministic**: same inputs always produce identical flags and actions.
* **Fully transparent**: every evaluated rule (pass or fail) is included in
  the output, not just triggered ones, providing a complete audit trace.
* **Config-driven**: rule thresholds are loaded from
  ``tools/config/compliance_rules.yaml`` — changing the config changes
  behaviour without touching code.
* **Rule evaluation trace**: intermediate values (ratio, ceiling, missing docs)
  are embedded in each flag description so decisions are fully self-explanatory.

Evaluation order (from config ``order`` field)
----------------------------------------------
1. MISSING_CRITICAL_FIELDS    — data integrity guard (CRITICAL)
2. REQUIRED_DOCUMENT_COMPLETENESS — document presence (CRITICAL)
3. LOAN_TO_INCOME_RATIO       — affordability (HIGH)
4. RISK_BAND_LOAN_CEILING     — band-specific ceiling (HIGH)

Action derivation
-----------------
Most-severe triggered flag determines the recommended action (config-driven):
  CRITICAL / HIGH → DECLINE
  MEDIUM          → REFER
  LOW             → APPROVE
  (no triggers)   → APPROVE
"""

from decimal import Decimal
from typing import Any

from shared.schemas import (
    ComplianceAction,
    ComplianceFlag,
    ComplianceResult,
    ComplianceSeverity,
    RiskProfile,
)
from tools.compliance_engine.config import CompliancePolicyConfig, RuleConfig, get_policy
from tools.log import get_logger

log = get_logger("compliance_engine")

_SEVERITY_RANK: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}


# ── Individual rule evaluators ───────────────────────────────────────────────

def _eval_missing_critical_fields(
    rule_cfg: RuleConfig,
    annual_income: Decimal,
    requested_loan_amount: Decimal,
) -> ComplianceFlag:
    """Evaluate MISSING_CRITICAL_FIELDS: zero/negative income or loan amount."""
    triggered = annual_income <= Decimal("0") or requested_loan_amount <= Decimal("0")
    desc = rule_cfg.description or (
        "One or more critical numeric fields (annual_income, requested_loan_amount) "
        "are zero or negative — possible data integrity issue or synthetic fraud indicator."
    )
    return ComplianceFlag(
        rule_id=rule_cfg.rule_id,
        description=desc,
        severity=ComplianceSeverity(rule_cfg.severity),
        triggered=triggered,
    )


def _eval_required_documents(
    rule_cfg: RuleConfig,
    document_types_present: list[str],
) -> ComplianceFlag:
    """Evaluate REQUIRED_DOCUMENT_COMPLETENESS: all required doc types present."""
    required = set(rule_cfg.required_document_types)
    present = set(document_types_present)
    missing = required - present
    triggered = bool(missing)
    if triggered:
        desc = (
            rule_cfg.description_template.format(missing_types=", ".join(sorted(missing)))
            if rule_cfg.description_template
            else f"Missing required document types: {', '.join(sorted(missing))}."
        )
    else:
        desc = rule_cfg.description_pass or "All required documents are present."
    return ComplianceFlag(
        rule_id=rule_cfg.rule_id,
        description=desc,
        severity=ComplianceSeverity(rule_cfg.severity),
        triggered=triggered,
    )


def _eval_loan_to_income_ratio(
    rule_cfg: RuleConfig,
    annual_income: Decimal,
    requested_loan_amount: Decimal,
) -> ComplianceFlag:
    """Evaluate LOAN_TO_INCOME_RATIO: loan must not exceed ``max_ratio`` × income."""
    if annual_income <= Decimal("0"):
        ratio = Decimal("9999")
    else:
        ratio = (requested_loan_amount / annual_income).quantize(Decimal("0.0001"))

    max_ratio = rule_cfg.max_ratio or Decimal("0.40")
    triggered = ratio > max_ratio
    desc = (
        f"Requested loan (${requested_loan_amount:,.0f}) is "
        f"{float(ratio):.1%} of annual income (${annual_income:,.0f}). "
        f"Policy limit: {float(max_ratio):.0%}."
    )
    return ComplianceFlag(
        rule_id=rule_cfg.rule_id,
        description=desc,
        severity=ComplianceSeverity(rule_cfg.severity),
        triggered=triggered,
    )


def _eval_risk_band_ceiling(
    rule_cfg: RuleConfig,
    risk_profile: RiskProfile,
    requested_loan_amount: Decimal,
) -> ComplianceFlag:
    """Evaluate RISK_BAND_LOAN_CEILING: loan must not exceed the band's max amount."""
    ceiling = rule_cfg.ceilings.get(risk_profile.value, Decimal("0"))
    triggered = requested_loan_amount > ceiling
    desc = (
        f"Requested loan (${requested_loan_amount:,.0f}) "
        + ("exceeds" if triggered else "is within")
        + f" the {risk_profile.value} ceiling of ${ceiling:,.0f}."
    )
    return ComplianceFlag(
        rule_id=rule_cfg.rule_id,
        description=desc,
        severity=ComplianceSeverity(rule_cfg.severity),
        triggered=triggered,
    )


# ── Action derivation ────────────────────────────────────────────────────────

def _derive_action(flags: list[ComplianceFlag], policy: CompliancePolicyConfig) -> ComplianceAction:
    """Derive the recommended action from the most severe triggered flag.

    Args:
        flags: All evaluated flags (pass + fail).
        policy: Loaded compliance policy for escalation mapping.

    Returns:
        :class:`~shared.schemas.ComplianceAction`.
    """
    triggered = [f for f in flags if f.triggered]
    if not triggered:
        return ComplianceAction(policy.action_escalation.NONE)

    max_rank = max(_SEVERITY_RANK.get(f.severity.value, 0) for f in triggered)
    severity_label = next(
        label for label, rank in sorted(_SEVERITY_RANK.items(), key=lambda x: -x[1]) if rank <= max_rank
    )

    action_str: str = getattr(policy.action_escalation, severity_label, "DECLINE")
    return ComplianceAction(action_str)


# ── Dispatch helper ──────────────────────────────────────────────────────────

def _evaluate_rule(
    rule_cfg: RuleConfig,
    annual_income: Decimal,
    requested_loan_amount: Decimal,
    risk_profile: RiskProfile,
    document_types_present: list[str],
) -> ComplianceFlag:
    """Dispatch a single rule evaluation by rule_id.

    Args:
        rule_cfg: Rule configuration loaded from YAML.
        annual_income: Applicant's annualised gross income.
        requested_loan_amount: Requested loan amount.
        risk_profile: Assigned risk band.
        document_types_present: Document types that completed parsing.

    Returns:
        :class:`~shared.schemas.ComplianceFlag` for this rule.

    Raises:
        ValueError: If the rule_id is unknown.
    """
    if rule_cfg.rule_id == "MISSING_CRITICAL_FIELDS":
        return _eval_missing_critical_fields(rule_cfg, annual_income, requested_loan_amount)
    if rule_cfg.rule_id == "REQUIRED_DOCUMENT_COMPLETENESS":
        return _eval_required_documents(rule_cfg, document_types_present)
    if rule_cfg.rule_id == "LOAN_TO_INCOME_RATIO":
        return _eval_loan_to_income_ratio(rule_cfg, annual_income, requested_loan_amount)
    if rule_cfg.rule_id == "RISK_BAND_LOAN_CEILING":
        return _eval_risk_band_ceiling(rule_cfg, risk_profile, requested_loan_amount)
    raise ValueError(f"Unknown compliance rule_id: {rule_cfg.rule_id!r}")


# ── Public entry point ───────────────────────────────────────────────────────

def evaluate(
    application_id: str,
    annual_income: Decimal,
    requested_loan_amount: Decimal,
    risk_profile: RiskProfile,
    document_types_present: list[str],
    applicant_name: str | None = None,
) -> ComplianceResult:
    """Run all compliance rules against one application (P4-T5).

    All rules are evaluated (no short-circuit) so the full audit trace is
    always available.  The ``applicant_name`` parameter is reserved for future
    duplicate-detection checks; it does not affect current rule outcomes.

    Args:
        application_id: Unique application identifier.
        annual_income: Annualised gross income in USD.
        requested_loan_amount: Requested loan amount in USD.
        risk_profile: Risk band from the risk engine.
        document_types_present: Document type strings that completed parsing.
        applicant_name: Applicant full name (reserved for duplicate detection).

    Returns:
        :class:`~shared.schemas.ComplianceResult` with full flag trace and
        recommended action.
    """
    policy = get_policy()
    ctx: dict[str, Any] = {"application_id": application_id}

    log.info(
        "starting compliance evaluation",
        correlation=ctx,
        risk_profile=risk_profile.value,
        document_count=len(document_types_present),
    )

    flags: list[ComplianceFlag] = []
    for rule_cfg in policy.ordered_rules():
        flag = _evaluate_rule(
            rule_cfg,
            annual_income,
            requested_loan_amount,
            risk_profile,
            document_types_present,
        )
        flags.append(flag)
        if flag.triggered:
            log.warning(
                "compliance rule triggered",
                correlation=ctx,
                rule_id=flag.rule_id,
                severity=flag.severity.value,
            )

    action = _derive_action(flags, policy)
    passed = action != ComplianceAction.DECLINE

    triggered_count = sum(1 for f in flags if f.triggered)
    log.info(
        "compliance evaluation complete",
        correlation=ctx,
        recommended_action=action.value,
        passed=passed,
        triggered_count=triggered_count,
        total_rules=len(flags),
    )

    return ComplianceResult(
        application_id=application_id,
        passed=passed,
        flags=flags,
        recommended_action=action,
    )
