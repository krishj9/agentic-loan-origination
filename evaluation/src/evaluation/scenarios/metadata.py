"""Scenario metadata models for test case organization and tracking.

Provides structured metadata for scenarios including:
- Unique identifiers and versioning
- Seed control for reproducibility
- Expected outcomes and dimensions
- Traceability to requirements
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ScenarioType(StrEnum):
    """Types of evaluation scenarios."""

    DOCUMENT_PARSING = "DOCUMENT_PARSING"
    RISK_SCORING = "RISK_SCORING"
    COMPLIANCE_EVALUATION = "COMPLIANCE_EVALUATION"
    END_TO_END = "END_TO_END"


class EvaluationDimension(StrEnum):
    """Dimensions along which scenarios are evaluated."""

    ACCURACY = "ACCURACY"  # Correctness of outputs
    DETERMINISM = "DETERMINISM"  # Reproducibility across runs
    EXPLAINABILITY = "EXPLAINABILITY"  # Quality of rationale/explanation
    COMPLETENESS = "COMPLETENESS"  # All required fields populated
    SCHEMA_CONFORMANCE = "SCHEMA_CONFORMANCE"  # Valid against canonical schemas
    BUSINESS_RULE_ADHERENCE = "BUSINESS_RULE_ADHERENCE"  # Follows configured rules
    EDGE_CASE_HANDLING = "EDGE_CASE_HANDLING"  # Behavior at boundaries
    ERROR_HANDLING = "ERROR_HANDLING"  # Graceful degradation


class ScenarioDimensions(BaseModel):
    """Evaluation dimensions applicable to a scenario."""

    model_config = ConfigDict(populate_by_name=True)

    primary_dimensions: list[EvaluationDimension] = Field(
        description="Primary evaluation dimensions for this scenario"
    )
    secondary_dimensions: list[EvaluationDimension] = Field(
        default_factory=list,
        description="Secondary/supporting evaluation dimensions",
    )


class ScenarioMetadata(BaseModel):
    """Metadata envelope for a test scenario.

    Provides:
    - Unique identification and versioning
    - Seed for deterministic randomization
    - Expected outcomes for validation
    - Evaluation dimensions being tested
    - Traceability to requirements/design
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "scenarioId": "risk_prime_001",
                "scenarioType": "RISK_SCORING",
                "version": "1.0.0",
                "seed": 42,
                "description": "PRIME band applicant with high income and low utilization",
                "createdAt": "2026-06-23T10:00:00Z",
                "expectedOutcomes": {
                    "riskProfile": "PRIME",
                    "creditScoreRange": [720, 800],
                    "decisionOutcome": "APPROVE",
                },
                "dimensions": {
                    "primaryDimensions": ["ACCURACY", "DETERMINISM"],
                    "secondaryDimensions": ["EXPLAINABILITY"],
                },
                "tags": ["golden-case", "prime", "approve"],
                "requirementRefs": ["REQ-5.3", "REQ-7.2"],
            }
        },
    )

    scenario_id: str = Field(
        alias="scenarioId",
        description="Unique identifier for the scenario (kebab-case recommended)",
    )
    scenario_type: ScenarioType = Field(
        alias="scenarioType",
        description="Type/category of the scenario",
    )
    version: str = Field(
        default="1.0.0",
        description="Semantic version of the scenario definition",
    )
    seed: int = Field(
        description=(
            "Deterministic seed for randomization. "
            "Same seed + scenario definition must produce identical outputs."
        ),
    )
    description: str = Field(
        description="Human-readable description of what this scenario tests"
    )
    created_at: datetime = Field(
        alias="createdAt",
        default_factory=datetime.utcnow,
        description="UTC timestamp when scenario was generated",
    )
    expected_outcomes: dict[str, object] = Field(
        alias="expectedOutcomes",
        description=(
            "Expected outcomes for validation. "
            "Structure varies by scenario type but must be JSON-serializable."
        ),
    )
    dimensions: ScenarioDimensions = Field(
        description="Evaluation dimensions this scenario is designed to test"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Classification tags for filtering and organization",
    )
    requirement_refs: list[str] = Field(
        default_factory=list,
        alias="requirementRefs",
        description="References to requirements/design sections (e.g. 'REQ-5.3', 'DESIGN-7.2')",
    )
