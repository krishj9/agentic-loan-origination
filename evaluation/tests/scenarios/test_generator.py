"""Tests for scenario generator.

Tests verify:
- Deterministic generation (same seed → same output)
- Schema conformance
- Expected outcomes structure
- Metadata completeness
"""

import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from shared.schemas import DecisionOutcome, DocumentType, RiskProfile

from evaluation.scenarios import ScenarioGenerator
from evaluation.scenarios.metadata import EvaluationDimension, ScenarioType


class TestScenarioGenerator:
    """Tests for ScenarioGenerator class."""

    @pytest.fixture
    def generator(self):
        """Provide a scenario generator instance."""
        return ScenarioGenerator(base_seed=42)

    def test_generator_initialization(self, generator):
        """Test that generator initializes correctly."""
        assert generator.base_seed == 42

    def test_generator_with_custom_seed(self):
        """Test generator with custom base seed."""
        generator = ScenarioGenerator(base_seed=100)
        assert generator.base_seed == 100


class TestDocumentParsingScenarios:
    """Tests for document parsing scenario generation."""

    @pytest.fixture
    def generator(self):
        return ScenarioGenerator(base_seed=42)

    def test_generate_paystub_scenario(self, generator):
        """Test paystub parsing scenario generation."""
        scenario = generator.generate_document_parsing_scenario(
            scenario_id="parse_paystub_001", document_type=DocumentType.PAYSTUB, seed=42
        )

        assert scenario.metadata.scenario_id == "parse_paystub_001"
        assert scenario.metadata.scenario_type == ScenarioType.DOCUMENT_PARSING
        assert scenario.metadata.seed == 42
        assert scenario.document_type == DocumentType.PAYSTUB
        assert scenario.expected_fields is not None

        # Verify paystub fields
        assert hasattr(scenario.expected_fields, "employee_name")
        assert hasattr(scenario.expected_fields, "gross_pay")

    def test_generate_bank_statement_scenario(self, generator):
        """Test bank statement parsing scenario generation."""
        scenario = generator.generate_document_parsing_scenario(
            scenario_id="parse_statement_001", document_type=DocumentType.BANK_STATEMENT, seed=42
        )

        assert scenario.metadata.scenario_id == "parse_statement_001"
        assert scenario.metadata.scenario_type == ScenarioType.DOCUMENT_PARSING
        assert scenario.document_type == DocumentType.BANK_STATEMENT
        assert scenario.expected_fields is not None

        # Verify bank statement fields
        assert hasattr(scenario.expected_fields, "account_holder_name")
        assert hasattr(scenario.expected_fields, "opening_balance")

    def test_paystub_scenario_determinism(self, generator):
        """Test that same seed produces identical paystub scenarios."""
        scenario1 = generator.generate_document_parsing_scenario(
            scenario_id="parse_test", document_type=DocumentType.PAYSTUB, seed=42
        )
        scenario2 = generator.generate_document_parsing_scenario(
            scenario_id="parse_test", document_type=DocumentType.PAYSTUB, seed=42
        )

        assert scenario1.expected_fields == scenario2.expected_fields
        assert scenario1.metadata.seed == scenario2.metadata.seed

    def test_paystub_scenario_metadata(self, generator):
        """Test paystub scenario metadata structure."""
        scenario = generator.generate_document_parsing_scenario(
            scenario_id="parse_paystub_meta", document_type=DocumentType.PAYSTUB, seed=100
        )

        metadata = scenario.metadata
        assert metadata.description is not None
        assert EvaluationDimension.ACCURACY in metadata.dimensions.primary_dimensions
        assert "document-parsing" in metadata.tags
        assert "REQ-6.1" in metadata.requirement_refs


class TestRiskScoringScenarios:
    """Tests for risk scoring scenario generation."""

    @pytest.fixture
    def generator(self):
        return ScenarioGenerator(base_seed=42)

    @pytest.mark.parametrize("risk_profile", [RiskProfile.PRIME, RiskProfile.NEAR_PRIME, RiskProfile.SUBPRIME])
    def test_generate_risk_scenario_for_each_profile(self, generator, risk_profile):
        """Test risk scenario generation for each profile."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id=f"risk_{risk_profile.value.lower()}_001", risk_profile=risk_profile, seed=42
        )

        assert scenario.metadata.scenario_type == ScenarioType.RISK_SCORING
        assert scenario.risk_request.risk_profile == risk_profile
        assert scenario.expected_response.risk_profile == risk_profile
        assert scenario.expected_risk_profile == risk_profile

    def test_prime_risk_scenario(self, generator):
        """Test PRIME risk scenario with expected score range."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="risk_prime_001", risk_profile=RiskProfile.PRIME, seed=42
        )

        # PRIME credit scores should be in 720-800 range
        assert 720 <= scenario.expected_response.credit_score <= 800
        assert scenario.expected_score_range == (720, 800)

        # PRIME should have reasonable income and low utilization
        assert scenario.risk_request.annual_income >= Decimal("80000")
        assert scenario.risk_request.debt_utilization < Decimal("0.30")

    def test_subprime_risk_scenario(self, generator):
        """Test SUBPRIME risk scenario with expected characteristics."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="risk_subprime_001", risk_profile=RiskProfile.SUBPRIME, seed=42
        )

        # SUBPRIME credit scores should be in 300-639 range
        assert 300 <= scenario.expected_response.credit_score <= 639
        assert scenario.expected_score_range == (300, 639)

        # SUBPRIME typically has lower income or higher utilization
        assert (
            scenario.risk_request.annual_income < Decimal("50000")
            or scenario.risk_request.debt_utilization > Decimal("0.60")
        )

    def test_risk_scenario_determinism(self, generator):
        """Test that same seed produces identical risk scenarios."""
        scenario1 = generator.generate_risk_scoring_scenario(
            scenario_id="risk_determinism", risk_profile=RiskProfile.PRIME, seed=42
        )
        scenario2 = generator.generate_risk_scoring_scenario(
            scenario_id="risk_determinism", risk_profile=RiskProfile.PRIME, seed=42
        )

        assert scenario1.risk_request == scenario2.risk_request
        assert scenario1.expected_response == scenario2.expected_response

    def test_risk_scenario_with_overrides(self, generator):
        """Test risk scenario with income and utilization overrides."""
        custom_income = Decimal("75000")
        custom_utilization = Decimal("0.25")

        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="risk_custom",
            risk_profile=RiskProfile.PRIME,
            seed=42,
            annual_income=custom_income,
            debt_utilization=custom_utilization,
        )

        assert scenario.risk_request.annual_income == custom_income
        assert scenario.risk_request.debt_utilization == custom_utilization

    def test_risk_scenario_tradelines(self, generator):
        """Test that risk scenarios include tradelines."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="risk_tradelines", risk_profile=RiskProfile.PRIME, seed=42
        )

        assert len(scenario.expected_response.tradelines) >= 2
        assert len(scenario.expected_response.tradelines) <= 5

        # Verify tradeline structure
        for tradeline in scenario.expected_response.tradelines:
            assert tradeline.balance >= 0
            assert tradeline.limit > 0
            assert 0 <= tradeline.utilization <= 1

    def test_risk_scenario_metadata(self, generator):
        """Test risk scenario metadata completeness."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="risk_meta", risk_profile=RiskProfile.NEAR_PRIME, seed=100
        )

        metadata = scenario.metadata
        assert EvaluationDimension.DETERMINISM in metadata.dimensions.primary_dimensions
        assert EvaluationDimension.EXPLAINABILITY in metadata.dimensions.primary_dimensions
        assert "risk-scoring" in metadata.tags
        assert "REQ-5.3" in metadata.requirement_refs


class TestComplianceScenarios:
    """Tests for compliance evaluation scenario generation."""

    @pytest.fixture
    def generator(self):
        return ScenarioGenerator(base_seed=42)

    def test_generate_compliance_scenario_with_flags(self, generator):
        """Test compliance scenario that triggers flags."""
        scenario = generator.generate_compliance_scenario(
            scenario_id="compliance_refer", seed=42, trigger_flags=True
        )

        assert scenario.metadata.scenario_type == ScenarioType.COMPLIANCE_EVALUATION
        assert "applicationId" in scenario.application_data
        assert "annualIncome" in scenario.application_data
        assert "requestedLoanAmount" in scenario.application_data

    def test_generate_compliance_scenario_clean(self, generator):
        """Test compliance scenario with no flags."""
        scenario = generator.generate_compliance_scenario(
            scenario_id="compliance_approve", seed=42, trigger_flags=False
        )

        assert scenario.metadata.scenario_type == ScenarioType.COMPLIANCE_EVALUATION
        # Clean scenario should have better loan-to-income ratio
        income = Decimal(scenario.application_data["annualIncome"])
        loan_amount = Decimal(scenario.application_data["requestedLoanAmount"])
        lti_ratio = loan_amount / income
        assert lti_ratio < 0.5  # Reasonable LTI

    def test_compliance_scenario_determinism(self, generator):
        """Test compliance scenario determinism."""
        scenario1 = generator.generate_compliance_scenario(scenario_id="compliance_det", seed=42, trigger_flags=True)
        scenario2 = generator.generate_compliance_scenario(scenario_id="compliance_det", seed=42, trigger_flags=True)

        assert scenario1.application_data == scenario2.application_data

    def test_compliance_scenario_metadata(self, generator):
        """Test compliance scenario metadata."""
        scenario = generator.generate_compliance_scenario(scenario_id="compliance_meta", seed=100, trigger_flags=True)

        metadata = scenario.metadata
        assert EvaluationDimension.BUSINESS_RULE_ADHERENCE in metadata.dimensions.primary_dimensions
        assert "compliance" in metadata.tags
        assert "REQ-5.4" in metadata.requirement_refs


class TestEndToEndScenarios:
    """Tests for end-to-end scenario generation."""

    @pytest.fixture
    def generator(self):
        return ScenarioGenerator(base_seed=42)

    @pytest.mark.parametrize(
        "risk_profile,expected_outcome",
        [
            (RiskProfile.PRIME, DecisionOutcome.APPROVE),
            (RiskProfile.NEAR_PRIME, DecisionOutcome.REFER),
            (RiskProfile.SUBPRIME, DecisionOutcome.DECLINE),
        ],
    )
    def test_generate_e2e_scenario_for_outcomes(self, generator, risk_profile, expected_outcome):
        """Test E2E scenario generation for different outcomes."""
        scenario = generator.generate_end_to_end_scenario(
            scenario_id=f"e2e_{expected_outcome.value.lower()}",
            risk_profile=risk_profile,
            expected_outcome=expected_outcome,
            seed=42,
        )

        assert scenario.metadata.scenario_type == ScenarioType.END_TO_END
        assert scenario.expected_risk_profile == risk_profile
        assert scenario.expected_decision_outcome == expected_outcome.value

    def test_e2e_scenario_canonical_application(self, generator):
        """Test E2E scenario includes canonical application."""
        scenario = generator.generate_end_to_end_scenario(
            scenario_id="e2e_app", risk_profile=RiskProfile.PRIME, expected_outcome=DecisionOutcome.APPROVE, seed=42
        )

        app = scenario.canonical_application
        assert app.application_id is not None
        assert app.applicant_name is not None
        assert app.annual_income > 0
        assert app.requested_loan_amount > 0
        assert 0 <= app.debt_utilization <= 1

    def test_e2e_scenario_document_fixtures(self, generator):
        """Test E2E scenario includes document fixtures."""
        scenario = generator.generate_end_to_end_scenario(
            scenario_id="e2e_docs", risk_profile=RiskProfile.PRIME, expected_outcome=DecisionOutcome.APPROVE, seed=42
        )

        assert len(scenario.document_fixtures) >= 2
        doc_types = [doc["type"] for doc in scenario.document_fixtures]
        assert "PAYSTUB" in doc_types
        assert "BANK_STATEMENT" in doc_types

    def test_e2e_scenario_determinism(self, generator):
        """Test E2E scenario determinism."""
        scenario1 = generator.generate_end_to_end_scenario(
            scenario_id="e2e_det", risk_profile=RiskProfile.PRIME, expected_outcome=DecisionOutcome.APPROVE, seed=42
        )
        scenario2 = generator.generate_end_to_end_scenario(
            scenario_id="e2e_det", risk_profile=RiskProfile.PRIME, expected_outcome=DecisionOutcome.APPROVE, seed=42
        )

        assert scenario1.canonical_application == scenario2.canonical_application
        assert scenario1.document_fixtures == scenario2.document_fixtures

    def test_e2e_scenario_metadata(self, generator):
        """Test E2E scenario metadata completeness."""
        scenario = generator.generate_end_to_end_scenario(
            scenario_id="e2e_meta", risk_profile=RiskProfile.PRIME, expected_outcome=DecisionOutcome.APPROVE, seed=100
        )

        metadata = scenario.metadata
        assert EvaluationDimension.COMPLETENESS in metadata.dimensions.primary_dimensions
        assert "golden-case" in metadata.tags
        assert "end-to-end" in metadata.tags
        assert len(metadata.requirement_refs) >= 3  # Should reference multiple requirements

    def test_e2e_approve_scenario_characteristics(self, generator):
        """Test that APPROVE E2E scenarios have appropriate characteristics."""
        scenario = generator.generate_end_to_end_scenario(
            scenario_id="e2e_approve_check",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=42,
        )

        # APPROVE scenarios should have reasonable loan amounts
        assert scenario.canonical_application.requested_loan_amount < Decimal("30000")

    def test_e2e_decline_scenario_characteristics(self, generator):
        """Test that DECLINE E2E scenarios have appropriate characteristics."""
        scenario = generator.generate_end_to_end_scenario(
            scenario_id="e2e_decline_check",
            risk_profile=RiskProfile.SUBPRIME,
            expected_outcome=DecisionOutcome.DECLINE,
            seed=42,
        )

        # DECLINE scenarios should have higher loan amounts relative to income
        lti_ratio = scenario.canonical_application.requested_loan_amount / scenario.canonical_application.annual_income
        assert lti_ratio > 0.5  # Higher LTI


class TestScenarioSerialization:
    """Tests for scenario saving and serialization."""

    @pytest.fixture
    def generator(self):
        return ScenarioGenerator(base_seed=42)

    def test_save_scenario_to_json(self, generator):
        """Test saving scenario to JSON file."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="save_test", risk_profile=RiskProfile.PRIME, seed=42
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "scenario.json"
            generator.save_scenario(scenario, output_path)

            assert output_path.exists()

            # Verify JSON is valid and loadable
            with open(output_path) as f:
                data = json.load(f)

            assert data["metadata"]["scenarioId"] == "save_test"
            assert data["metadata"]["scenarioType"] == "RISK_SCORING"

    def test_saved_scenario_has_camelcase_aliases(self, generator):
        """Test that saved scenarios use camelCase aliases."""
        scenario = generator.generate_risk_scoring_scenario(
            scenario_id="camel_test", risk_profile=RiskProfile.PRIME, seed=42
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "scenario.json"
            generator.save_scenario(scenario, output_path)

            with open(output_path) as f:
                data = json.load(f)

            # Check for camelCase keys
            assert "scenarioId" in data["metadata"]
            assert "scenarioType" in data["metadata"]
            assert "riskRequest" in data
