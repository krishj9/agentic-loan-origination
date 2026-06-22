"""Bootstrap tests for shared canonical schemas.

These tests verify that:
  1. All schema modules import cleanly from the package.
  2. Models can be instantiated from valid data.
  3. JSON round-trips preserve all field values.
  4. Enum members match the string values expected by external contracts.

Run with:
    uv run pytest shared/tests/
"""

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from shared.schemas import (
    AuditContext,
    BankStatementFields,
    CanonicalApplication,
    ComplianceFlag,
    ComplianceResult,
    Decision,
    PayStubFields,
    RiskRequest,
    RiskResponse,
    Tradeline,
    Transaction,
)
from shared.schemas.enums import (
    AccountType,
    ApplicationStatus,
    ComplianceAction,
    ComplianceSeverity,
    DecisionOutcome,
    DocumentType,
    RiskFlag,
    RiskProfile,
)

# ── Enum contract tests ───────────────────────────────────────────────────


def test_risk_profile_values() -> None:
    assert RiskProfile.PRIME == "PRIME"
    assert RiskProfile.NEAR_PRIME == "NEAR_PRIME"
    assert RiskProfile.SUBPRIME == "SUBPRIME"


def test_decision_outcome_values() -> None:
    assert DecisionOutcome.APPROVE == "APPROVE"
    assert DecisionOutcome.REFER == "REFER"
    assert DecisionOutcome.DECLINE == "DECLINE"


def test_document_type_values() -> None:
    assert DocumentType.PAYSTUB == "PAYSTUB"
    assert DocumentType.BANK_STATEMENT == "BANK_STATEMENT"


def test_account_type_values() -> None:
    assert AccountType.CREDIT_CARD == "CREDIT_CARD"
    assert AccountType.AUTO_LOAN == "AUTO_LOAN"
    assert AccountType.MORTGAGE == "MORTGAGE"


def test_risk_flag_values() -> None:
    assert RiskFlag.HIGH_UTILIZATION == "HIGH_UTILIZATION"
    assert RiskFlag.LOW_INCOME == "LOW_INCOME"


# ── AuditContext ─────────────────────────────────────────────────────────


def test_audit_context_round_trip() -> None:
    now = datetime(2026, 6, 22, 18, 0, 0, tzinfo=UTC)
    ctx = AuditContext(
        application_id="app_123",
        user_id="user_abc",
        submission_timestamp=now,
        decision_timestamp=now,
        runtime_session_id="session_xyz",
        trace_id="trace_001",
    )
    data = json.loads(ctx.model_dump_json())
    assert data["application_id"] == "app_123"
    assert data["user_id"] == "user_abc"
    assert data["runtime_session_id"] == "session_xyz"


def test_audit_context_optional_fields() -> None:
    ctx = AuditContext(
        application_id="app_456",
        user_id="user_def",
        submission_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert ctx.decision_timestamp is None
    assert ctx.runtime_session_id is None
    assert ctx.trace_id is None


# ── Document models ──────────────────────────────────────────────────────


def test_pay_stub_fields_instantiation() -> None:
    stub = PayStubFields(
        employee_name="Jane Smith",
        employer_name="Acme Corp",
        pay_period_start=date(2026, 5, 1),
        pay_period_end=date(2026, 5, 31),
        pay_date=date(2026, 6, 1),
        gross_pay=Decimal("7083.33"),
        deductions=Decimal("2083.33"),
        net_pay=Decimal("5000.00"),
    )
    assert stub.employee_name == "Jane Smith"
    assert stub.gross_pay == Decimal("7083.33")
    assert stub.ytd_gross_pay is None


def test_bank_statement_fields_with_transactions() -> None:
    tx = Transaction(
        date=date(2026, 5, 15),
        description="Grocery Store",
        amount=Decimal("-45.00"),
    )
    stmt = BankStatementFields(
        account_holder_name="Jane Smith",
        statement_period_start=date(2026, 5, 1),
        statement_period_end=date(2026, 5, 31),
        account_number_masked="****1234",
        opening_balance=Decimal("10000.00"),
        closing_balance=Decimal("9955.00"),
        transactions=[tx],
    )
    assert len(stmt.transactions) == 1
    assert stmt.transactions[0].amount == Decimal("-45.00")


# ── Risk schemas ─────────────────────────────────────────────────────────


def test_risk_request_with_override() -> None:
    req = RiskRequest(
        applicantId="app_prime_001",
        annualIncome=Decimal("90000.00"),
        debtUtilization=Decimal("0.20"),
        riskProfile=RiskProfile.PRIME,
    )
    assert req.risk_profile == RiskProfile.PRIME
    assert req.annual_income == Decimal("90000.00")


def test_risk_request_no_override() -> None:
    req = RiskRequest(
        applicantId="app_001",
        annualIncome=Decimal("90000.00"),
        debtUtilization=Decimal("0.20"),
    )
    assert req.risk_profile is None


def test_risk_response_json_round_trip() -> None:
    tradeline = Tradeline(
        accountType=AccountType.CREDIT_CARD,
        balance=Decimal("2500.00"),
        limit=Decimal("10000.00"),
        utilization=Decimal("0.25"),
    )
    resp = RiskResponse(
        applicantId="app_001",
        riskProfile=RiskProfile.PRIME,
        creditScore=745,
        tradelines=[tradeline],
        riskFlags=[],
        incomeBand="HIGH",
        utilizationBand="LOW",
        scoreRangeRationale="Annual income > 80,000 and debt utilization < 30% → PRIME (720–800).",
    )
    data = json.loads(resp.model_dump_json(by_alias=True))
    assert data["riskProfile"] == "PRIME"
    assert data["creditScore"] == 745
    assert data["tradelines"][0]["accountType"] == "CREDIT_CARD"


# ── Compliance schemas ───────────────────────────────────────────────────


def test_compliance_result_approve() -> None:
    result = ComplianceResult(
        applicationId="app_001",
        passed=True,
        flags=[],
        recommendedAction=ComplianceAction.APPROVE,
    )
    assert result.passed is True
    assert result.recommended_action == ComplianceAction.APPROVE


def test_compliance_result_with_flag() -> None:
    flag = ComplianceFlag(
        rule_id="LOAN_TO_INCOME_RATIO",
        description="Requested loan exceeds 5× annual income.",
        severity=ComplianceSeverity.HIGH,
        triggered=True,
    )
    result = ComplianceResult(
        applicationId="app_002",
        passed=False,
        flags=[flag],
        recommendedAction=ComplianceAction.DECLINE,
    )
    assert result.passed is False
    assert result.flags[0].triggered is True


# ── CanonicalApplication ─────────────────────────────────────────────────


def test_canonical_application_defaults() -> None:
    app = CanonicalApplication(
        applicationId="app_001",
        userId="user_abc",
        applicantName="Jane Smith",
        annualIncome=Decimal("85000.00"),
        requestedLoanAmount=Decimal("20000.00"),
        debtUtilization=Decimal("0.25"),
    )
    assert app.status == ApplicationStatus.PENDING
    assert app.document_inventory == []
    assert app.pay_stub_data is None
    assert app.bank_statement_data is None
    assert app.audit_context is None


def test_canonical_application_json_uses_aliases() -> None:
    app = CanonicalApplication(
        applicationId="app_001",
        userId="user_abc",
        applicantName="Jane Smith",
        annualIncome=Decimal("85000.00"),
        requestedLoanAmount=Decimal("20000.00"),
        debtUtilization=Decimal("0.25"),
    )
    data = json.loads(app.model_dump_json(by_alias=True))
    assert "applicationId" in data
    assert "annualIncome" in data
    assert "debtUtilization" in data


# ── Decision ─────────────────────────────────────────────────────────────


def test_decision_minimal() -> None:
    decision = Decision(
        applicationId="app_001",
        outcome=DecisionOutcome.APPROVE,
        riskProfile=RiskProfile.PRIME,
        creditScore=745,
        rationale="Income band HIGH, utilization band LOW. No compliance flags.",
    )
    assert decision.outcome == DecisionOutcome.APPROVE
    assert decision.artifact_json_s3_key is None


def test_decision_json_uses_aliases() -> None:
    decision = Decision(
        applicationId="app_001",
        outcome=DecisionOutcome.DECLINE,
        riskProfile=RiskProfile.SUBPRIME,
        creditScore=520,
        rationale="Income band LOW. HIGH_UTILIZATION flag raised.",
    )
    data = json.loads(decision.model_dump_json(by_alias=True))
    assert data["applicationId"] == "app_001"
    assert data["outcome"] == "DECLINE"
    assert data["riskProfile"] == "SUBPRIME"


# ── Package-level import ─────────────────────────────────────────────────


def test_all_exports_importable() -> None:
    """Smoke test: the shared.schemas package __init__ exports all types."""
    from shared.schemas import __all__ as schema_exports

    expected = {
        "RiskProfile",
        "DecisionOutcome",
        "DocumentType",
        "AuditContext",
        "PayStubFields",
        "BankStatementFields",
        "CanonicalApplication",
        "RiskRequest",
        "RiskResponse",
        "ComplianceResult",
        "Decision",
    }
    assert expected.issubset(set(schema_exports))
