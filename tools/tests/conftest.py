"""Test fixtures and shared helpers for the tools package tests."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from shared.schemas import (
    AuditContext,
    ComplianceAction,
    ComplianceFlag,
    ComplianceResult,
    ComplianceSeverity,
    Decision,
    DecisionOutcome,
    RiskFlag,
    RiskProfile,
    RiskRequest,
    RiskResponse,
    Tradeline,
    AccountType,
)


@pytest.fixture
def prime_request() -> RiskRequest:
    return RiskRequest(
        applicant_id="test-prime-001",
        annual_income=Decimal("95000.00"),
        debt_utilization=Decimal("0.20"),
    )


@pytest.fixture
def near_prime_request() -> RiskRequest:
    return RiskRequest(
        applicant_id="test-near-prime-001",
        annual_income=Decimal("60000.00"),
        debt_utilization=Decimal("0.45"),
    )


@pytest.fixture
def subprime_request() -> RiskRequest:
    return RiskRequest(
        applicant_id="test-subprime-001",
        annual_income=Decimal("30000.00"),
        debt_utilization=Decimal("0.75"),
    )


@pytest.fixture
def audit_context() -> AuditContext:
    return AuditContext(
        application_id="app-test-001",
        user_id="user-cognito-sub-001",
        submission_timestamp=datetime(2026, 6, 22, 18, 0, 0, tzinfo=timezone.utc),
        decision_timestamp=datetime(2026, 6, 22, 18, 0, 45, tzinfo=timezone.utc),
        runtime_session_id="session-xyz-001",
        trace_id="trace-abc-001",
    )


@pytest.fixture
def sample_risk_response() -> RiskResponse:
    return RiskResponse(
        applicant_id="app-test-001",
        risk_profile=RiskProfile.PRIME,
        credit_score=745,
        tradelines=[
            Tradeline(
                account_type=AccountType.CREDIT_CARD,
                balance=Decimal("2500.00"),
                limit=Decimal("10000.00"),
                utilization=Decimal("0.25"),
            )
        ],
        risk_flags=[],
        income_band="HIGH",
        utilization_band="LOW",
        score_range_rationale="Annual income HIGH ($95,000), debt utilisation LOW (20%). Assigned PRIME — score 745.",
    )


@pytest.fixture
def sample_compliance_result() -> ComplianceResult:
    return ComplianceResult(
        application_id="app-test-001",
        passed=True,
        flags=[
            ComplianceFlag(
                rule_id="LOAN_TO_INCOME_RATIO",
                description="Requested loan ($20,000) is 21.1% of annual income ($95,000). Limit: 40%.",
                severity=ComplianceSeverity.HIGH,
                triggered=False,
            )
        ],
        recommended_action=ComplianceAction.APPROVE,
    )


@pytest.fixture
def sample_decision(sample_risk_response: RiskResponse, sample_compliance_result: ComplianceResult) -> Decision:
    return Decision(
        application_id="app-test-001",
        outcome=DecisionOutcome.APPROVE,
        risk_profile=RiskProfile.PRIME,
        credit_score=745,
        rationale="Income band HIGH, utilisation LOW. No compliance flags triggered.",
        risk_response=sample_risk_response,
        compliance_result=sample_compliance_result,
        artifact_json_s3_key="archive/app-test-001/decision.json",
        artifact_pdf_s3_key="archive/app-test-001/decision.pdf",
    )
