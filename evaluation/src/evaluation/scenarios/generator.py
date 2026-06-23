"""Scenario generator for creating structured, deterministic test cases.

Implements P6-T1: Synthetic scenario generator producing test cases for:
- Document parsing
- Risk scoring
- Compliance evaluation
- End-to-end loan origination flows

All scenarios are deterministic, reproducible, and typed using canonical schemas.
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from shared.schemas import (
    AccountType,
    ApplicationStatus,
    BankStatementFields,
    CanonicalApplication,
    ComplianceAction,
    ComplianceSeverity,
    DecisionOutcome,
    DocumentType,
    PayStubFields,
    RiskFlag,
    RiskProfile,
    RiskRequest,
    RiskResponse,
    Transaction,
    Tradeline,
)

from evaluation.scenarios.metadata import (
    EvaluationDimension,
    ScenarioDimensions,
    ScenarioMetadata,
    ScenarioType,
)
from evaluation.scenarios.models import (
    ComplianceScenario,
    DocumentParsingScenario,
    EndToEndScenario,
    RiskScoringScenario,
)
from evaluation.scenarios.seed_control import SeedContext, generate_deterministic_id, seeded_context

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    """Generate deterministic, reproducible test scenarios.

    All generation is seeded and uses canonical schemas. Scenarios include
    metadata with correlation IDs, expected outcomes, and evaluation dimensions.
    """

    def __init__(self, base_seed: int = 42) -> None:
        """Initialize scenario generator.

        Args:
            base_seed: Base seed for all scenario generation (default: 42)
        """
        self.base_seed = base_seed
        logger.info(
            "ScenarioGenerator initialized",
            extra={"base_seed": base_seed},
        )

    def generate_document_parsing_scenario(
        self,
        scenario_id: str,
        document_type: DocumentType,
        seed: int | None = None,
    ) -> DocumentParsingScenario:
        """Generate a document parsing scenario.

        Args:
            scenario_id: Unique identifier for the scenario
            document_type: Type of document (PAYSTUB or BANK_STATEMENT)
            seed: Optional seed override (uses base_seed + scenario_id if not provided)

        Returns:
            DocumentParsingScenario with metadata and expected fields
        """
        scenario_seed = seed if seed is not None else self.base_seed
        seed_ctx = SeedContext(base_seed=scenario_seed, scenario_id=scenario_id, component="document")

        with seeded_context(seed_ctx) as rng:
            if document_type == DocumentType.PAYSTUB:
                expected_fields = self._generate_paystub_fields(rng, scenario_id)
                description = f"Paystub parsing for {expected_fields.employee_name}"
            elif document_type == DocumentType.BANK_STATEMENT:
                expected_fields = self._generate_bank_statement_fields(rng, scenario_id)
                description = f"Bank statement parsing for {expected_fields.account_holder_name}"
            else:
                raise ValueError(f"Unsupported document type for parsing scenario: {document_type}")

        metadata = ScenarioMetadata(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.DOCUMENT_PARSING,
            seed=scenario_seed,
            description=description,
            expected_outcomes={
                "documentType": document_type.value,
                "fieldsExtracted": len(expected_fields.model_dump(exclude_none=True)),
            },
            dimensions=ScenarioDimensions(
                primary_dimensions=[
                    EvaluationDimension.ACCURACY,
                    EvaluationDimension.COMPLETENESS,
                    EvaluationDimension.SCHEMA_CONFORMANCE,
                ]
            ),
            tags=["document-parsing", document_type.value.lower()],
            requirement_refs=["REQ-6.1"],
        )

        logger.info(
            "Generated document parsing scenario",
            extra={
                "scenario_id": scenario_id,
                "document_type": document_type.value,
                "seed": scenario_seed,
            },
        )

        return DocumentParsingScenario(
            metadata=metadata,
            document_type=document_type,
            expected_fields=expected_fields,
        )

    def generate_risk_scoring_scenario(
        self,
        scenario_id: str,
        risk_profile: RiskProfile,
        seed: int | None = None,
        annual_income: Decimal | None = None,
        debt_utilization: Decimal | None = None,
    ) -> RiskScoringScenario:
        """Generate a risk scoring scenario for a specific risk profile.

        Args:
            scenario_id: Unique identifier for the scenario
            risk_profile: Target risk profile (PRIME, NEAR_PRIME, SUBPRIME)
            seed: Optional seed override
            annual_income: Optional income override (generated if not provided)
            debt_utilization: Optional utilization override (generated if not provided)

        Returns:
            RiskScoringScenario with request and expected response
        """
        scenario_seed = seed if seed is not None else self.base_seed
        seed_ctx = SeedContext(base_seed=scenario_seed, scenario_id=scenario_id, component="risk")

        with seeded_context(seed_ctx) as rng:
            # Generate income and utilization based on risk profile if not provided
            if annual_income is None:
                annual_income = self._generate_income_for_profile(rng, risk_profile)
            if debt_utilization is None:
                debt_utilization = self._generate_utilization_for_profile(rng, risk_profile)

            applicant_id = generate_deterministic_id("app", scenario_seed)

            # Create risk request
            risk_request = RiskRequest(
                applicant_id=applicant_id,
                annual_income=annual_income,
                debt_utilization=debt_utilization,
                risk_profile=risk_profile,  # Override to ensure deterministic profile
            )

            # Generate expected response structure
            credit_score, score_range = self._generate_score_for_profile(rng, risk_profile)
            tradelines = self._generate_tradelines(rng, applicant_id, debt_utilization)
            risk_flags = self._determine_risk_flags(annual_income, debt_utilization, risk_profile)

            expected_response = RiskResponse(
                applicant_id=applicant_id,
                risk_profile=risk_profile,
                credit_score=credit_score,
                tradelines=tradelines,
                risk_flags=risk_flags,
                income_band=self._classify_income(annual_income),
                utilization_band=self._classify_utilization(debt_utilization),
                score_range_rationale=f"Risk profile {risk_profile.value} with income ${annual_income:,.0f} and utilization {debt_utilization:.0%}",
            )

        metadata = ScenarioMetadata(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.RISK_SCORING,
            seed=scenario_seed,
            description=f"{risk_profile.value} risk profile scenario: ${annual_income:,.0f} income, {debt_utilization:.0%} utilization",
            expected_outcomes={
                "riskProfile": risk_profile.value,
                "creditScoreRange": list(score_range),
                "tradelineCount": len(tradelines),
            },
            dimensions=ScenarioDimensions(
                primary_dimensions=[
                    EvaluationDimension.ACCURACY,
                    EvaluationDimension.DETERMINISM,
                    EvaluationDimension.EXPLAINABILITY,
                ],
                secondary_dimensions=[EvaluationDimension.SCHEMA_CONFORMANCE],
            ),
            tags=["risk-scoring", risk_profile.value.lower()],
            requirement_refs=["REQ-5.3", "DESIGN-7"],
        )

        logger.info(
            "Generated risk scoring scenario",
            extra={
                "scenario_id": scenario_id,
                "risk_profile": risk_profile.value,
                "credit_score": credit_score,
                "seed": scenario_seed,
            },
        )

        return RiskScoringScenario(
            metadata=metadata,
            risk_request=risk_request,
            expected_response=expected_response,
            expected_risk_profile=risk_profile,
            expected_score_range=score_range,
        )

    def generate_compliance_scenario(
        self,
        scenario_id: str,
        seed: int | None = None,
        trigger_flags: bool = True,
    ) -> ComplianceScenario:
        """Generate a compliance evaluation scenario.

        Args:
            scenario_id: Unique identifier for the scenario
            seed: Optional seed override
            trigger_flags: Whether to generate data that triggers compliance flags

        Returns:
            ComplianceScenario with application data and expected results
        """
        scenario_seed = seed if seed is not None else self.base_seed
        seed_ctx = SeedContext(base_seed=scenario_seed, scenario_id=scenario_id, component="compliance")

        with seeded_context(seed_ctx) as rng:
            applicant_id = generate_deterministic_id("app", scenario_seed)

            if trigger_flags:
                # Generate data that will trigger compliance flags
                annual_income = Decimal(rng.uniform(30000, 50000))
                requested_loan_amount = Decimal(rng.uniform(25000, 40000))  # High LTI ratio
                expected_action = ComplianceAction.REFER
                description = "Compliance scenario triggering REFER due to high loan-to-income ratio"
            else:
                # Generate clean data
                annual_income = Decimal(rng.uniform(75000, 100000))
                requested_loan_amount = Decimal(rng.uniform(15000, 25000))  # Reasonable LTI
                expected_action = ComplianceAction.APPROVE
                description = "Compliance scenario with no triggered flags (APPROVE)"

            application_data = {
                "applicationId": applicant_id,
                "annualIncome": str(annual_income),
                "requestedLoanAmount": str(requested_loan_amount),
                "debtUtilization": str(Decimal(rng.uniform(0.1, 0.4))),
            }

        metadata = ScenarioMetadata(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.COMPLIANCE_EVALUATION,
            seed=scenario_seed,
            description=description,
            expected_outcomes={
                "recommendedAction": expected_action.value,
                "loanToIncomeRatio": float(requested_loan_amount / annual_income),
            },
            dimensions=ScenarioDimensions(
                primary_dimensions=[
                    EvaluationDimension.BUSINESS_RULE_ADHERENCE,
                    EvaluationDimension.ACCURACY,
                ],
                secondary_dimensions=[EvaluationDimension.DETERMINISM],
            ),
            tags=["compliance", expected_action.value.lower()],
            requirement_refs=["REQ-5.4", "DESIGN-8"],
        )

        logger.info(
            "Generated compliance scenario",
            extra={
                "scenario_id": scenario_id,
                "expected_action": expected_action.value,
                "seed": scenario_seed,
            },
        )

        return ComplianceScenario(
            metadata=metadata,
            application_data=application_data,
        )

    def generate_end_to_end_scenario(
        self,
        scenario_id: str,
        risk_profile: RiskProfile,
        expected_outcome: DecisionOutcome,
        seed: int | None = None,
    ) -> EndToEndScenario:
        """Generate an end-to-end loan origination flow scenario.

        Args:
            scenario_id: Unique identifier for the scenario
            risk_profile: Target risk profile
            expected_outcome: Expected final decision outcome
            seed: Optional seed override

        Returns:
            EndToEndScenario with complete application flow
        """
        scenario_seed = seed if seed is not None else self.base_seed
        seed_ctx = SeedContext(base_seed=scenario_seed, scenario_id=scenario_id, component="e2e")

        with seeded_context(seed_ctx) as rng:
            applicant_id = generate_deterministic_id("app", scenario_seed)
            applicant_names = ["Alice Johnson", "Bob Martinez", "Carol Chen", "David Brown", "Emma Wilson"]
            applicant_name = rng.choice(applicant_names)

            # Generate financial data aligned with risk profile and expected outcome
            annual_income = self._generate_income_for_profile(rng, risk_profile)
            debt_utilization = self._generate_utilization_for_profile(rng, risk_profile)

            # Adjust loan amount based on expected outcome
            if expected_outcome == DecisionOutcome.APPROVE:
                requested_loan_amount = Decimal(rng.uniform(10000, 25000))
            elif expected_outcome == DecisionOutcome.REFER:
                requested_loan_amount = Decimal(rng.uniform(25000, 35000))
            else:  # DECLINE
                requested_loan_amount = Decimal(rng.uniform(35000, 50000))

            canonical_application = CanonicalApplication(
                application_id=applicant_id,
                user_id=f"user_{rng.randint(1000, 9999)}",
                applicant_name=applicant_name,
                annual_income=annual_income,
                requested_loan_amount=requested_loan_amount,
                debt_utilization=debt_utilization,
                status=ApplicationStatus.PENDING,
            )

            # Document fixtures
            document_fixtures = [
                {"type": "PAYSTUB", "path": f"fixtures/{risk_profile.value.lower()}/paystub_{scenario_id}.pdf"},
                {
                    "type": "BANK_STATEMENT",
                    "path": f"fixtures/{risk_profile.value.lower()}/statement_{scenario_id}.pdf",
                },
            ]

        metadata = ScenarioMetadata(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.END_TO_END,
            seed=scenario_seed,
            description=f"E2E {expected_outcome.value} scenario for {risk_profile.value} applicant: {applicant_name}",
            expected_outcomes={
                "decisionOutcome": expected_outcome.value,
                "riskProfile": risk_profile.value,
                "complianceAction": expected_outcome.value,  # Simplified mapping
            },
            dimensions=ScenarioDimensions(
                primary_dimensions=[
                    EvaluationDimension.ACCURACY,
                    EvaluationDimension.COMPLETENESS,
                    EvaluationDimension.DETERMINISM,
                ],
                secondary_dimensions=[
                    EvaluationDimension.EXPLAINABILITY,
                    EvaluationDimension.SCHEMA_CONFORMANCE,
                ],
            ),
            tags=["end-to-end", "golden-case", risk_profile.value.lower(), expected_outcome.value.lower()],
            requirement_refs=["REQ-5.1", "REQ-5.3", "REQ-5.4", "DESIGN-5"],
        )

        logger.info(
            "Generated end-to-end scenario",
            extra={
                "scenario_id": scenario_id,
                "risk_profile": risk_profile.value,
                "expected_outcome": expected_outcome.value,
                "seed": scenario_seed,
            },
        )

        return EndToEndScenario(
            metadata=metadata,
            canonical_application=canonical_application,
            document_fixtures=document_fixtures,
            expected_risk_profile=risk_profile,
            expected_compliance_action=expected_outcome.value,
            expected_decision_outcome=expected_outcome.value,
        )

    def save_scenario(self, scenario: Any, output_path: Path) -> None:
        """Save a scenario to JSON file.

        Args:
            scenario: Scenario instance to save
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(scenario.model_dump(by_alias=True), f, indent=2, default=str)

        logger.info(
            "Saved scenario to file",
            extra={
                "scenario_id": scenario.metadata.scenario_id,
                "output_path": str(output_path),
            },
        )

    # Private helper methods

    def _generate_paystub_fields(self, rng: Any, scenario_id: str) -> PayStubFields:
        """Generate synthetic paystub fields."""
        employee_names = ["Jane Smith", "John Doe", "Maria Garcia", "James Wilson"]
        employer_names = ["Acme Corp", "TechStart Inc", "Global Finance LLC", "City Services"]

        pay_period_end = date.today()
        pay_period_start = pay_period_end - timedelta(days=14)  # Bi-weekly
        pay_date = pay_period_end + timedelta(days=3)

        gross_pay = Decimal(rng.uniform(2500, 5000))
        deductions = Decimal(rng.uniform(500, 1200))
        net_pay = gross_pay - deductions

        return PayStubFields(
            employee_name=rng.choice(employee_names),
            employer_name=rng.choice(employer_names),
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            pay_date=pay_date,
            gross_pay=gross_pay,
            deductions=deductions,
            net_pay=net_pay,
            ytd_gross_pay=gross_pay * Decimal(12),  # Simplified
            ytd_net_pay=net_pay * Decimal(12),
        )

    def _generate_bank_statement_fields(self, rng: Any, scenario_id: str) -> BankStatementFields:
        """Generate synthetic bank statement fields."""
        account_holder_names = ["Jane Smith", "John Doe", "Maria Garcia", "James Wilson"]

        statement_period_end = date.today()
        statement_period_start = statement_period_end - timedelta(days=30)

        opening_balance = Decimal(rng.uniform(1000, 10000))
        closing_balance = Decimal(rng.uniform(1000, 10000))

        # Generate some transactions
        transactions = []
        for i in range(rng.randint(5, 15)):
            trans_date = statement_period_start + timedelta(days=rng.randint(0, 30))
            amount = Decimal(rng.uniform(-500, 1000))
            transactions.append(
                Transaction(
                    transaction_date=trans_date,
                    description=rng.choice(["Purchase", "Deposit", "Withdrawal", "Transfer"]),
                    amount=amount,
                )
            )

        return BankStatementFields(
            account_holder_name=rng.choice(account_holder_names),
            statement_period_start=statement_period_start,
            statement_period_end=statement_period_end,
            account_number_masked="****1234",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            transactions=transactions,
        )

    def _generate_income_for_profile(self, rng: Any, profile: RiskProfile) -> Decimal:
        """Generate annual income appropriate for risk profile."""
        if profile == RiskProfile.PRIME:
            return Decimal(rng.uniform(80000, 120000))
        elif profile == RiskProfile.NEAR_PRIME:
            return Decimal(rng.uniform(50000, 79999))
        else:  # SUBPRIME
            return Decimal(rng.uniform(25000, 49999))

    def _generate_utilization_for_profile(self, rng: Any, profile: RiskProfile) -> Decimal:
        """Generate debt utilization appropriate for risk profile."""
        if profile == RiskProfile.PRIME:
            return Decimal(rng.uniform(0.05, 0.30))
        elif profile == RiskProfile.NEAR_PRIME:
            return Decimal(rng.uniform(0.30, 0.60))
        else:  # SUBPRIME
            return Decimal(rng.uniform(0.60, 0.90))

    def _generate_score_for_profile(self, rng: Any, profile: RiskProfile) -> tuple[int, tuple[int, int]]:
        """Generate credit score and range for risk profile."""
        if profile == RiskProfile.PRIME:
            score_range = (720, 800)
        elif profile == RiskProfile.NEAR_PRIME:
            score_range = (640, 719)
        else:  # SUBPRIME
            score_range = (300, 639)

        score = rng.randint(score_range[0], score_range[1])
        return score, score_range

    def _generate_tradelines(self, rng: Any, applicant_id: str, utilization: Decimal) -> list[Tradeline]:
        """Generate synthetic tradelines."""
        tradeline_count = rng.randint(2, 5)
        tradelines = []

        account_types = [AccountType.CREDIT_CARD, AccountType.AUTO_LOAN, AccountType.MORTGAGE]

        for _ in range(tradeline_count):
            account_type = rng.choice(account_types)
            limit = Decimal(rng.uniform(5000, 50000))
            balance = limit * Decimal(rng.uniform(float(utilization) * 0.5, float(utilization) * 1.5))
            tradeline_util = min(balance / limit, Decimal(1.0))

            tradelines.append(
                Tradeline(
                    account_type=account_type,
                    balance=balance,
                    limit=limit,
                    utilization=tradeline_util,
                )
            )

        return tradelines

    def _determine_risk_flags(
        self, annual_income: Decimal, debt_utilization: Decimal, profile: RiskProfile
    ) -> list[RiskFlag]:
        """Determine risk flags based on inputs."""
        flags = []

        if debt_utilization > Decimal("0.50"):
            flags.append(RiskFlag.HIGH_UTILIZATION)
        elif debt_utilization > Decimal("0.30"):
            flags.append(RiskFlag.MODERATE_UTILIZATION)

        if annual_income < Decimal("40000"):
            flags.append(RiskFlag.LOW_INCOME)
        elif profile == RiskProfile.NEAR_PRIME:
            flags.append(RiskFlag.NEAR_PRIME_INCOME)

        return flags

    def _classify_income(self, annual_income: Decimal) -> str:
        """Classify income into band."""
        if annual_income >= Decimal("80000"):
            return "HIGH"
        elif annual_income >= Decimal("50000"):
            return "MID"
        else:
            return "LOW"

    def _classify_utilization(self, debt_utilization: Decimal) -> str:
        """Classify utilization into band."""
        if debt_utilization < Decimal("0.30"):
            return "LOW"
        elif debt_utilization < Decimal("0.60"):
            return "MODERATE"
        else:
            return "HIGH"
