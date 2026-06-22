"""Compliance engine input/output schemas.

The compliance engine (agents/tools/compliance.py, Phase 4) runs
deterministic, rule-based checks from `config/compliance_rules.yaml`.
Rules can run either as an internal LangGraph node or as a Gateway tool
(design §8).

Outputs are structured pass/fail + flags + recommended action (requirements §5.4).
"""

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas.enums import ComplianceAction, ComplianceSeverity


class ComplianceFlag(BaseModel):
    """A single triggered or evaluated compliance rule result."""

    model_config = ConfigDict(populate_by_name=True)

    rule_id: str = Field(description="Stable identifier for the compliance rule (e.g. 'LOAN_TO_INCOME_RATIO').")
    description: str = Field(description="Human-readable description of the rule and why it triggered.")
    severity: ComplianceSeverity = Field(description="Severity of the flag if triggered.")
    triggered: bool = Field(description="True if the rule found a violation; False if the check passed.")


class ComplianceResult(BaseModel):
    """Output of a full compliance evaluation for one application.

    The `recommended_action` reflects the most severe triggered flag:
      DECLINE  → at least one CRITICAL or HIGH-severity flag triggered.
      REFER    → at least one MEDIUM-severity flag triggered.
      APPROVE  → no flags triggered, or all LOW-severity.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicationId": "app_01J000000000000000000000",
                "passed": True,
                "flags": [],
                "recommendedAction": "APPROVE",
            }
        },
    )

    application_id: str = Field(alias="applicationId", description="Application this result belongs to.")
    passed: bool = Field(description="True only if no CRITICAL or HIGH flags were triggered.")
    flags: list[ComplianceFlag] = Field(
        default_factory=list,
        description="All evaluated compliance rules with their individual results.",
    )
    recommended_action: ComplianceAction = Field(
        alias="recommendedAction",
        description="Recommended underwriting action based on the most severe triggered flag.",
    )
