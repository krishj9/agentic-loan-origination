"""Risk engine request / response schemas.

The mock risk engine (agents/tools/risk_engine.py, Phase 4) is exposed via
AgentCore Gateway as `risk_engine.evaluate` with the exact JSON contract
defined in requirements §5.3 and design §7.2.

The supervisor and credit risk subgraph treat the mock response as if it
came from an external provider — the architectural contract remains
production-like (design §7.1).
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas.enums import AccountType, RiskFlag, RiskProfile


class Tradeline(BaseModel):
    """A single synthetic tradeline entry in the risk response.

    Tradelines are generated deterministically from a seed derived from
    `applicant_id` as described in design §7.6.
    """

    model_config = ConfigDict(populate_by_name=True)

    account_type: AccountType = Field(alias="accountType", description="Type of the credit account.")
    balance: Decimal = Field(description="Current outstanding balance (USD).")
    limit: Decimal = Field(description="Credit limit or original loan amount (USD).")
    utilization: Decimal = Field(
        description="Utilisation ratio for this tradeline (0.0 – 1.0).",
    )


class RiskRequest(BaseModel):
    """Input contract for `risk_engine.evaluate`.

    The optional `risk_profile` field allows golden-case tests and
    evaluation harness runs to pin a specific band, bypassing the
    scoring rules (design §7.5 override support).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicantId": "app_01J000000000000000000000",
                "annualIncome": "85000.00",
                "debtUtilization": "0.25",
            }
        },
    )

    applicant_id: str = Field(
        alias="applicantId",
        description="Application / applicant identifier used to seed deterministic tradeline generation.",
    )
    annual_income: Decimal = Field(
        alias="annualIncome",
        description="Annualised gross income (USD). Drives PRIME / NEAR_PRIME / SUBPRIME classification.",
    )
    debt_utilization: Decimal = Field(
        alias="debtUtilization",
        description="Aggregate debt utilisation ratio (0.0 – 1.0).",
    )
    risk_profile: RiskProfile | None = Field(
        default=None,
        alias="riskProfile",
        description=(
            "Optional override for the risk profile bucket. "
            "When set, scoring rules are bypassed and this band is returned directly. "
            "Use for golden-case replay tests only."
        ),
    )


class RiskResponse(BaseModel):
    """Output contract for `risk_engine.evaluate`.

    Matches the JSON schema in requirements §5.3 exactly, extended with
    explainability fields required by design §7.7.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicantId": "app_01J000000000000000000000",
                "riskProfile": "PRIME",
                "creditScore": 745,
                "tradelines": [
                    {
                        "accountType": "CREDIT_CARD",
                        "balance": "2500.00",
                        "limit": "10000.00",
                        "utilization": "0.25",
                    }
                ],
                "riskFlags": [],
                "incomeBand": "HIGH",
                "utilizationBand": "LOW",
                "scoreRangeRationale": "Annual income > 80,000 and debt utilization < 30% → PRIME band (720–800).",
            }
        },
    )

    applicant_id: str = Field(alias="applicantId", description="Mirrors the request applicant_id.")
    risk_profile: RiskProfile = Field(alias="riskProfile", description="Assigned risk bucket.")
    credit_score: int = Field(
        alias="creditScore",
        description="Deterministic synthetic credit score within the band's configured range.",
    )
    tradelines: list[Tradeline] = Field(
        default_factory=list,
        description="1–5 synthetic tradelines generated from the applicant_id seed.",
    )
    risk_flags: list[RiskFlag] = Field(
        alias="riskFlags",
        default_factory=list,
        description="Flags raised by the scoring rules (e.g. HIGH_UTILIZATION, LOW_INCOME).",
    )

    # Explainability fields (design §7.7)
    income_band: str = Field(
        alias="incomeBand",
        description="Income classification label used in the decision rationale (HIGH / MID / LOW).",
    )
    utilization_band: str = Field(
        alias="utilizationBand",
        description="Utilisation classification label (LOW / MODERATE / HIGH).",
    )
    score_range_rationale: str = Field(
        alias="scoreRangeRationale",
        description="Human-readable explanation of how the risk profile and score were assigned.",
    )
