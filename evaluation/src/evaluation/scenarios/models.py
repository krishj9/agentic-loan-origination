"""Scenario data models for different test case types.

Defines typed scenario structures for:
- Document parsing scenarios
- Risk scoring scenarios
- Compliance evaluation scenarios
- End-to-end loan origination flows

All scenarios include metadata and use canonical schemas.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas import (
    BankStatementFields,
    CanonicalApplication,
    ComplianceResult,
    DocumentType,
    PayStubFields,
    RiskProfile,
    RiskRequest,
    RiskResponse,
)

from evaluation.scenarios.metadata import ScenarioMetadata


class Scenario(BaseModel):
    """Base scenario model with common metadata."""

    model_config = ConfigDict(populate_by_name=True)

    metadata: ScenarioMetadata = Field(
        description="Scenario metadata including ID, seed, expected outcomes, and dimensions"
    )


class DocumentParsingScenario(Scenario):
    """Scenario for testing document parsing and normalization.

    Tests LlamaParse extraction followed by normalization to canonical schema.
    Can include synthetic PDF metadata or fixture references.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "metadata": {
                    "scenarioId": "parse_paystub_001",
                    "scenarioType": "DOCUMENT_PARSING",
                    "seed": 100,
                    "description": "Standard bi-weekly paystub parsing",
                    "expectedOutcomes": {"fieldsExtracted": 10, "confidenceLevel": "high"},
                    "dimensions": {
                        "primaryDimensions": ["ACCURACY", "COMPLETENESS"],
                    },
                },
                "documentType": "PAYSTUB",
                "documentFixturePath": "fixtures/paystubs/standard_biweekly.pdf",
                "expectedFields": {
                    "employeeName": "Jane Smith",
                    "employerName": "Acme Corp",
                    "grossPay": "3500.00",
                },
            }
        },
    )

    document_type: DocumentType = Field(
        alias="documentType",
        description="Type of document being tested",
    )
    document_fixture_path: str | None = Field(
        default=None,
        alias="documentFixturePath",
        description="Path to synthetic PDF fixture if using file-based testing",
    )
    synthetic_content: dict[str, object] | None = Field(
        default=None,
        alias="syntheticContent",
        description="Synthetic document content for generation-based testing",
    )
    expected_fields: PayStubFields | BankStatementFields | None = Field(
        default=None,
        alias="expectedFields",
        description="Expected extracted and normalized fields",
    )


class RiskScoringScenario(Scenario):
    """Scenario for testing deterministic risk engine evaluation.

    Provides risk request input and expected risk response for validation.
    Tests determinism, score calculation, tradeline generation, and explainability.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "metadata": {
                    "scenarioId": "risk_prime_high_income",
                    "scenarioType": "RISK_SCORING",
                    "seed": 42,
                    "description": "PRIME applicant: $90k income, 20% utilization",
                    "expectedOutcomes": {
                        "riskProfile": "PRIME",
                        "creditScoreRange": [720, 800],
                    },
                    "dimensions": {
                        "primaryDimensions": ["ACCURACY", "DETERMINISM", "EXPLAINABILITY"],
                    },
                },
                "riskRequest": {
                    "applicantId": "app_prime_001",
                    "annualIncome": "90000.00",
                    "debtUtilization": "0.20",
                },
                "expectedResponse": {
                    "applicantId": "app_prime_001",
                    "riskProfile": "PRIME",
                    "creditScore": 750,
                },
            }
        },
    )

    risk_request: RiskRequest = Field(
        alias="riskRequest",
        description="Input to the risk engine evaluate function",
    )
    expected_response: RiskResponse | None = Field(
        default=None,
        alias="expectedResponse",
        description="Expected risk response for validation (complete or partial)",
    )
    expected_risk_profile: RiskProfile | None = Field(
        default=None,
        alias="expectedRiskProfile",
        description="Expected risk profile when full response not specified",
    )
    expected_score_range: tuple[int, int] | None = Field(
        default=None,
        alias="expectedScoreRange",
        description="Expected credit score range [min, max]",
    )


class ComplianceScenario(Scenario):
    """Scenario for testing rule-based compliance evaluation.

    Provides application data and expected compliance result including flags,
    severity, and recommended action.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "metadata": {
                    "scenarioId": "compliance_high_lti",
                    "scenarioType": "COMPLIANCE_EVALUATION",
                    "seed": 200,
                    "description": "High loan-to-income ratio triggering REFER",
                    "expectedOutcomes": {
                        "recommendedAction": "REFER",
                        "flagCount": 1,
                    },
                    "dimensions": {
                        "primaryDimensions": ["BUSINESS_RULE_ADHERENCE", "ACCURACY"],
                    },
                },
                "applicationData": {
                    "applicationId": "app_comp_001",
                    "annualIncome": "50000.00",
                    "requestedLoanAmount": "30000.00",
                },
                "expectedResult": {
                    "applicationId": "app_comp_001",
                    "passed": False,
                    "recommendedAction": "REFER",
                },
            }
        },
    )

    application_data: dict[str, object] = Field(
        alias="applicationData",
        description="Application/financial data input for compliance checks",
    )
    expected_result: ComplianceResult | None = Field(
        default=None,
        alias="expectedResult",
        description="Expected compliance evaluation result",
    )


class EndToEndScenario(Scenario):
    """End-to-end loan origination flow scenario.

    Tests the complete pipeline: application intake → document parsing →
    risk evaluation → compliance → decision → packaging.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "metadata": {
                    "scenarioId": "e2e_approve_prime",
                    "scenarioType": "END_TO_END",
                    "seed": 500,
                    "description": "End-to-end PRIME approval flow",
                    "expectedOutcomes": {
                        "decisionOutcome": "APPROVE",
                        "riskProfile": "PRIME",
                        "complianceAction": "APPROVE",
                    },
                    "dimensions": {
                        "primaryDimensions": ["ACCURACY", "COMPLETENESS", "DETERMINISM"],
                        "secondaryDimensions": ["EXPLAINABILITY"],
                    },
                    "tags": ["golden-case", "approve", "prime"],
                    "requirementRefs": ["REQ-5.1", "REQ-5.3", "REQ-5.4"],
                },
                "canonicalApplication": {
                    "applicationId": "app_e2e_001",
                    "applicantName": "Alice Johnson",
                    "annualIncome": "85000.00",
                    "requestedLoanAmount": "20000.00",
                    "debtUtilization": "0.25",
                },
                "documentFixtures": [
                    {"type": "PAYSTUB", "path": "fixtures/prime/paystub_alice_01.pdf"},
                    {"type": "BANK_STATEMENT", "path": "fixtures/prime/statement_alice_01.pdf"},
                ],
            }
        },
    )

    canonical_application: CanonicalApplication = Field(
        alias="canonicalApplication",
        description="Initial application data",
    )
    document_fixtures: list[dict[str, str]] = Field(
        alias="documentFixtures",
        description="List of document fixtures with type and path",
    )
    expected_risk_profile: RiskProfile | None = Field(
        default=None,
        alias="expectedRiskProfile",
        description="Expected risk profile from evaluation",
    )
    expected_compliance_action: str | None = Field(
        default=None,
        alias="expectedComplianceAction",
        description="Expected compliance recommended action",
    )
    expected_decision_outcome: str | None = Field(
        default=None,
        alias="expectedDecisionOutcome",
        description="Expected final decision outcome",
    )
