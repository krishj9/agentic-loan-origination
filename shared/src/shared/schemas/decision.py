"""Final decision schema written to S3 archive and returned to the API caller.

The decision is the machine-readable artifact produced by the `make_decision`
node in the supervisor graph (design §5.1, §9.1).  A human-readable PDF is
generated alongside it by the packaging subgraph.

Design constraints:
  - Business-critical decisions must NOT depend solely on unconstrained LLM
    prose (requirements §5.1).  The `rationale` is assembled from explicit
    rule-based explanations sourced from RiskResponse.score_range_rationale
    and ComplianceResult.flags.
  - The artifact must include full audit metadata for S3 archive (design §4.4).
"""

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas.audit import AuditContext
from shared.schemas.compliance import ComplianceResult
from shared.schemas.enums import DecisionOutcome, RiskProfile
from shared.schemas.risk import RiskResponse


class Decision(BaseModel):
    """Final underwriting decision for a loan application.

    Written to `archive/{application_id}/decision.json` with the full
    audit context attached.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicationId": "app_01J000000000000000000000",
                "outcome": "APPROVE",
                "riskProfile": "PRIME",
                "creditScore": 745,
                "rationale": "Income band HIGH, utilization band LOW. No compliance flags triggered.",
                "artifactJsonS3Key": "archive/app_01J000000000000000000000/decision.json",
                "artifactPdfS3Key": "archive/app_01J000000000000000000000/decision.pdf",
            }
        },
    )

    application_id: str = Field(alias="applicationId", description="Application this decision belongs to.")
    outcome: DecisionOutcome = Field(description="Final underwriting outcome (APPROVE / REFER / DECLINE).")
    risk_profile: RiskProfile = Field(alias="riskProfile", description="Risk band assigned by the risk engine.")
    credit_score: int = Field(alias="creditScore", description="Synthetic credit score from the risk engine.")
    rationale: str = Field(
        description=(
            "Rule-based decision rationale assembled from risk-engine explanations "
            "and compliance results. Never invented LLM prose."
        ),
    )

    # Full nested results for audit trail
    risk_response: RiskResponse | None = Field(
        default=None,
        alias="riskResponse",
        description="Full risk engine response included for audit and replay.",
    )
    compliance_result: ComplianceResult | None = Field(
        default=None,
        alias="complianceResult",
        description="Full compliance evaluation result included for audit and replay.",
    )

    # S3 artifact references written by the packaging subgraph
    artifact_json_s3_key: str | None = Field(
        default=None,
        alias="artifactJsonS3Key",
        description="S3 key of the archived machine-readable decision JSON.",
    )
    artifact_pdf_s3_key: str | None = Field(
        default=None,
        alias="artifactPdfS3Key",
        description="S3 key of the archived human-readable decision PDF.",
    )

    # Audit envelope — required in every S3 archive artifact (design §4.4)
    audit_context: AuditContext | None = Field(
        default=None,
        alias="auditContext",
        description="Audit metadata (user_id, timestamps, session/trace IDs).",
    )
