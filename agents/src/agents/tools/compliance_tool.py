"""Compliance-engine tool interface — ``compliance_engine.evaluate`` (P3-T10).

Defines the Pydantic v2 request/response wrappers and the callable invoked
by the compliance subgraph.  Delegates to the Phase 4 rule engine
(``agents.tools.compliance``) when available; falls back to a deterministic
stub that enforces the design §8 rules so graph tests remain reproducible.

All compliance logic is deterministic — same inputs always produce the same
flags and recommended action.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas import (
    ComplianceAction,
    ComplianceFlag,
    ComplianceResult,
    ComplianceSeverity,
    RiskProfile,
)

# ── Request / Response models ───────────────────────────────────────────────

class ComplianceToolRequest(BaseModel):
    """Input contract for ``compliance_engine.evaluate``."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Application identifier.")
    annual_income: Decimal = Field(description="Annualised gross income in USD.")
    requested_loan_amount: Decimal = Field(description="Requested loan amount in USD.")
    risk_profile: RiskProfile = Field(description="Risk band assigned by the risk engine.")
    document_types_present: list[str] = Field(
        description="Document types that completed parsing (e.g. ['PAYSTUB', 'BANK_STATEMENT']).",
    )
    applicant_name: str | None = Field(
        default=None,
        description="Applicant name for duplicate-detection checks.",
    )


class ComplianceToolResponse(BaseModel):
    """Output contract for ``compliance_engine.evaluate``."""

    model_config = ConfigDict(populate_by_name=True)

    compliance_result: ComplianceResult = Field(description="Full compliance evaluation result.")


# ── Rule constants (mirrors config/compliance_rules.yaml, Phase 4) ──────────

_MAX_LOAN_TO_INCOME_RATIO = Decimal("0.40")  # 40 % of annual income
_RISK_BAND_LOAN_CEILINGS: dict[RiskProfile, Decimal] = {
    RiskProfile.PRIME: Decimal("100000"),
    RiskProfile.NEAR_PRIME: Decimal("50000"),
    RiskProfile.SUBPRIME: Decimal("20000"),
}
_REQUIRED_DOC_TYPES = {"PAYSTUB", "BANK_STATEMENT"}


# ── Stub rule evaluations ───────────────────────────────────────────────────

def _check_loan_to_income(request: ComplianceToolRequest) -> ComplianceFlag:
    ratio = request.requested_loan_amount / request.annual_income if request.annual_income else Decimal("9999")
    triggered = ratio > _MAX_LOAN_TO_INCOME_RATIO
    return ComplianceFlag(
        rule_id="LOAN_TO_INCOME_RATIO",
        description=(
            f"Requested loan ({request.requested_loan_amount:,.0f}) is "
            f"{float(ratio):.1%} of annual income ({request.annual_income:,.0f}). "
            f"Limit: {float(_MAX_LOAN_TO_INCOME_RATIO):.0%}."
        ),
        severity=ComplianceSeverity.HIGH,
        triggered=triggered,
    )


def _check_risk_band_ceiling(request: ComplianceToolRequest) -> ComplianceFlag:
    ceiling = _RISK_BAND_LOAN_CEILINGS.get(request.risk_profile, Decimal("0"))
    triggered = request.requested_loan_amount > ceiling
    return ComplianceFlag(
        rule_id="RISK_BAND_LOAN_CEILING",
        description=(
            f"Requested loan ({request.requested_loan_amount:,.0f}) exceeds the "
            f"{request.risk_profile} ceiling of {ceiling:,.0f}."
        ),
        severity=ComplianceSeverity.HIGH,
        triggered=triggered,
    )


def _check_required_documents(request: ComplianceToolRequest) -> ComplianceFlag:
    present = set(request.document_types_present)
    missing = _REQUIRED_DOC_TYPES - present
    triggered = bool(missing)
    return ComplianceFlag(
        rule_id="REQUIRED_DOCUMENT_COMPLETENESS",
        description=(
            f"Missing required document types: {', '.join(sorted(missing))}."
            if triggered
            else "All required documents are present."
        ),
        severity=ComplianceSeverity.CRITICAL,
        triggered=triggered,
    )


def _check_missing_critical_fields(request: ComplianceToolRequest) -> ComplianceFlag:
    """Flag applications with zero income or zero loan amount as suspicious."""
    triggered = request.annual_income <= Decimal("0") or request.requested_loan_amount <= Decimal("0")
    return ComplianceFlag(
        rule_id="MISSING_CRITICAL_FIELDS",
        description=(
            "One or more critical numeric fields (annual_income, requested_loan_amount) "
            "are zero or negative — possible data integrity issue."
        ),
        severity=ComplianceSeverity.CRITICAL,
        triggered=triggered,
    )


def _derive_action(flags: list[ComplianceFlag]) -> ComplianceAction:
    """Derive the recommended action from the most severe triggered flag."""
    triggered = [f for f in flags if f.triggered]
    if not triggered:
        return ComplianceAction.APPROVE
    severities = {f.severity for f in triggered}
    if ComplianceSeverity.CRITICAL in severities or ComplianceSeverity.HIGH in severities:
        return ComplianceAction.DECLINE
    if ComplianceSeverity.MEDIUM in severities:
        return ComplianceAction.REFER
    return ComplianceAction.APPROVE


def _stub_evaluate(request: ComplianceToolRequest) -> ComplianceResult:
    """Deterministic stub evaluation applying design §8 rules."""
    flags: list[ComplianceFlag] = [
        _check_missing_critical_fields(request),
        _check_required_documents(request),
        _check_loan_to_income(request),
        _check_risk_band_ceiling(request),
    ]
    action = _derive_action(flags)
    passed = action != ComplianceAction.DECLINE
    return ComplianceResult(
        application_id=request.application_id,
        passed=passed,
        flags=flags,
        recommended_action=action,
    )


def call_compliance_engine(request: ComplianceToolRequest) -> ComplianceResult:
    """Run compliance checks against the application.

    Delegates to the Phase 4 engine (``tools.compliance_engine.evaluate``)
    when available; uses the local rule stub otherwise.

    Args:
        request: Validated ``ComplianceToolRequest``.

    Returns:
        ``ComplianceResult`` with all evaluated flags and recommended action.
    """
    try:
        from tools.compliance_engine import evaluate  # Phase 4

        return evaluate(
            application_id=request.application_id,
            annual_income=request.annual_income,
            requested_loan_amount=request.requested_loan_amount,
            risk_profile=request.risk_profile,
            document_types_present=request.document_types_present,
            applicant_name=request.applicant_name,
        )
    except ImportError:
        return _stub_evaluate(request)


def get_tool_spec() -> dict[str, Any] | None:
    """Return the Gateway tool specification for this tool."""
    from agents.tools.schemas import COMPLIANCE_ENGINE_TOOL_SPEC

    return COMPLIANCE_ENGINE_TOOL_SPEC
