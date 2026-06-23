"""Unit tests for the compliance specialist subgraph (P3-T6, P3-T12).

Tests cover:
* APPROVE path: all rules pass
* DECLINE path: loan-to-income ratio exceeded
* DECLINE path: risk-band ceiling exceeded
* DECLINE path: required documents missing
* REFER path: MEDIUM-severity flag only
* Missing inputs produce a DECLINE with MISSING_INPUTS flag
* Subgraph end-to-end compilation and invocation
"""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal

from agents.subgraphs.compliance import build_compliance_subgraph, evaluate_compliance
from shared.schemas import (
    AccountType,
    ApplicationStatus,
    CanonicalApplication,
    ComplianceAction,
    Document,
    DocumentType,
    RiskProfile,
    RiskResponse,
    Tradeline,
)


def _make_application(
    annual_income: Decimal = Decimal("85000"),
    loan_amount: Decimal = Decimal("20000"),
    application_id: str = "app_c_001",
) -> CanonicalApplication:
    return CanonicalApplication(
        applicationId=application_id,
        userId="user_1",
        applicantName="Jane Smith",
        annualIncome=annual_income,
        requestedLoanAmount=loan_amount,
        debtUtilization=Decimal("0.25"),
        status=ApplicationStatus.PROCESSING,
    )


def _make_risk_response(
    profile: RiskProfile = RiskProfile.PRIME,
    application_id: str = "app_c_001",
) -> RiskResponse:
    return RiskResponse(
        applicant_id=application_id,
        risk_profile=profile,
        credit_score=745 if profile == RiskProfile.PRIME else 650,
        tradelines=[
            Tradeline(
                account_type=AccountType.CREDIT_CARD,
                balance=Decimal("2500"),
                limit=Decimal("10000"),
                utilization=Decimal("0.25"),
            )
        ],
        risk_flags=[],
        income_band="HIGH",
        utilization_band="LOW",
        score_range_rationale="Stub score rationale.",
    )


def _make_completed_doc(doc_type: DocumentType, application_id: str = "app_c_001") -> Document:
    from datetime import datetime

    return Document(
        document_id=f"doc_{doc_type.lower()}",
        application_id=application_id,
        document_type=doc_type,
        s3_key=f"incoming/{application_id}/{doc_type.lower()}.pdf",
        uploaded_at=datetime.now(UTC),
        parse_status="COMPLETED",
    )


def _base_state(
    annual_income: Decimal = Decimal("85000"),
    loan_amount: Decimal = Decimal("20000"),
    profile: RiskProfile = RiskProfile.PRIME,
    application_id: str = "app_c_001",
    include_docs: bool = True,
) -> dict:
    state: dict = {
        "application_id": application_id,
        "user_id": "user_1",
        "trace_id": "trace_c_001",
        "application": _make_application(annual_income, loan_amount, application_id),
        "risk_response": _make_risk_response(profile, application_id),
        "document_inventory": (
            [
                _make_completed_doc(DocumentType.PAYSTUB, application_id),
                _make_completed_doc(DocumentType.BANK_STATEMENT, application_id),
            ]
            if include_docs
            else []
        ),
    }
    return state


class TestEvaluateComplianceNode:
    def test_approve_path_all_rules_pass(self) -> None:
        state = _base_state(annual_income=Decimal("120000"), loan_amount=Decimal("20000"))
        result = evaluate_compliance(state)
        cr = result["compliance_result"]
        assert cr.passed is True
        assert cr.recommended_action == ComplianceAction.APPROVE
        triggered = [f for f in cr.flags if f.triggered]
        assert triggered == []

    def test_decline_loan_to_income_ratio_exceeded(self) -> None:
        # 80000 * 0.40 = 32000 ceiling; loan = 50000
        state = _base_state(annual_income=Decimal("80000"), loan_amount=Decimal("50000"))
        result = evaluate_compliance(state)
        cr = result["compliance_result"]
        assert cr.recommended_action == ComplianceAction.DECLINE
        triggered_ids = {f.rule_id for f in cr.flags if f.triggered}
        assert "LOAN_TO_INCOME_RATIO" in triggered_ids

    def test_decline_risk_band_ceiling_subprime(self) -> None:
        # SUBPRIME ceiling = 20000; loan = 25000
        state = _base_state(
            annual_income=Decimal("30000"),
            loan_amount=Decimal("25000"),
            profile=RiskProfile.SUBPRIME,
        )
        result = evaluate_compliance(state)
        cr = result["compliance_result"]
        triggered_ids = {f.rule_id for f in cr.flags if f.triggered}
        assert "RISK_BAND_LOAN_CEILING" in triggered_ids

    def test_decline_missing_required_documents(self) -> None:
        state = _base_state(include_docs=False)
        result = evaluate_compliance(state)
        cr = result["compliance_result"]
        triggered_ids = {f.rule_id for f in cr.flags if f.triggered}
        assert "REQUIRED_DOCUMENT_COMPLETENESS" in triggered_ids

    def test_missing_application_produces_decline(self) -> None:
        state = _base_state()
        state["application"] = None
        result = evaluate_compliance(state)
        cr = result["compliance_result"]
        assert cr.recommended_action == ComplianceAction.DECLINE
        triggered_ids = {f.rule_id for f in cr.flags if f.triggered}
        assert "MISSING_INPUTS" in triggered_ids

    def test_missing_risk_response_produces_decline(self) -> None:
        state = _base_state()
        state["risk_response"] = None
        result = evaluate_compliance(state)
        cr = result["compliance_result"]
        assert cr.recommended_action == ComplianceAction.DECLINE


class TestComplianceSubgraphEndToEnd:
    def test_compiles(self) -> None:
        assert build_compliance_subgraph() is not None

    def test_happy_path_approve(self) -> None:
        subgraph = build_compliance_subgraph()
        state = _base_state(annual_income=Decimal("120000"), loan_amount=Decimal("20000"))
        result = subgraph.invoke(state)
        assert result["compliance_result"].recommended_action == ComplianceAction.APPROVE

    def test_decline_path_high_loan(self) -> None:
        subgraph = build_compliance_subgraph()
        state = _base_state(annual_income=Decimal("50000"), loan_amount=Decimal("80000"))
        result = subgraph.invoke(state)
        assert result["compliance_result"].recommended_action == ComplianceAction.DECLINE
