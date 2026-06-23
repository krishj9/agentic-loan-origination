"""Unit tests for the risk specialist subgraph (P3-T5, P3-T12).

Tests cover:
* build_risk_request derives income from pay stub when present
* build_risk_request falls back to application.annual_income
* evaluate_risk produces a valid RiskResponse with explainability fields
* Subgraph end-to-end: happy path for each risk band
* Determinism: same input → identical RiskResponse
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from agents.subgraphs.risk import build_risk_request, build_risk_subgraph, evaluate_risk
from shared.schemas import ApplicationStatus, CanonicalApplication, RiskProfile


def _make_application(
    annual_income: Decimal = Decimal("85000"),
    debt_utilization: Decimal = Decimal("0.25"),
    loan_amount: Decimal = Decimal("20000"),
    application_id: str = "app_risk_001",
) -> CanonicalApplication:
    return CanonicalApplication(
        applicationId=application_id,
        userId="user_1",
        applicantName="Jane Smith",
        annualIncome=annual_income,
        requestedLoanAmount=loan_amount,
        debtUtilization=debt_utilization,
        status=ApplicationStatus.PROCESSING,
    )


def _base_state(
    annual_income: Decimal = Decimal("85000"),
    debt_utilization: Decimal = Decimal("0.25"),
    application_id: str = "app_risk_001",
) -> dict:
    return {
        "application_id": application_id,
        "user_id": "user_1",
        "trace_id": "trace_risk_001",
        "application": _make_application(annual_income, debt_utilization, application_id=application_id),
        "pay_stub_data": None,
        "risk_request": None,
        "risk_response": None,
    }


class TestBuildRiskRequestNode:
    def test_uses_application_annual_income(self) -> None:
        state = _base_state(annual_income=Decimal("90000"))
        result = build_risk_request(state)
        assert result["risk_request"] is not None
        assert result["risk_request"].annual_income == Decimal("90000")

    def test_derives_income_from_paystub_when_present(self) -> None:
        from datetime import date

        from shared.schemas import PayStubFields

        state = _base_state(annual_income=Decimal("50000"))
        state["pay_stub_data"] = PayStubFields(
            employee_name="Jane",
            employer_name="Acme",
            pay_period_start=date(2026, 5, 1),
            pay_period_end=date(2026, 5, 31),
            pay_date=date(2026, 6, 1),
            gross_pay=Decimal("7000.00"),
            deductions=Decimal("1400.00"),
            net_pay=Decimal("5600.00"),
        )
        result = build_risk_request(state)
        # 7000 * 12 = 84000
        assert result["risk_request"].annual_income == Decimal("84000.00")

    def test_applicant_id_matches_application_id(self) -> None:
        state = _base_state(application_id="app_xyz")
        result = build_risk_request(state)
        assert result["risk_request"].applicant_id == "app_xyz"


class TestEvaluateRiskNode:
    def test_risk_response_produced(self) -> None:
        from shared.schemas import RiskRequest

        state = _base_state(annual_income=Decimal("90000"), debt_utilization=Decimal("0.20"))
        state["risk_request"] = RiskRequest(
            applicant_id="app_risk_001",
            annual_income=Decimal("90000"),
            debt_utilization=Decimal("0.20"),
        )
        result = evaluate_risk(state)
        assert result.get("risk_response") is not None

    def test_no_risk_request_returns_empty(self) -> None:
        state = _base_state()
        state["risk_request"] = None
        result = evaluate_risk(state)
        assert result == {}

    def test_risk_response_has_explainability_fields(self) -> None:
        from shared.schemas import RiskRequest

        state = _base_state(annual_income=Decimal("90000"), debt_utilization=Decimal("0.20"))
        state["risk_request"] = RiskRequest(
            applicant_id="app_risk_001",
            annual_income=Decimal("90000"),
            debt_utilization=Decimal("0.20"),
        )
        result = evaluate_risk(state)
        rr = result["risk_response"]
        assert rr.income_band in ("HIGH", "MID", "LOW")
        assert rr.utilization_band in ("LOW", "MODERATE", "HIGH")
        assert rr.score_range_rationale != ""


class TestRiskSubgraphEndToEnd:
    def test_compiles(self) -> None:
        assert build_risk_subgraph() is not None

    @pytest.mark.parametrize(
        "annual_income,debt_utilization,expected_profile",
        [
            (Decimal("90000"), Decimal("0.20"), RiskProfile.PRIME),
            (Decimal("60000"), Decimal("0.40"), RiskProfile.NEAR_PRIME),
            (Decimal("30000"), Decimal("0.70"), RiskProfile.SUBPRIME),
        ],
    )
    def test_correct_profile_by_band(
        self,
        annual_income: Decimal,
        debt_utilization: Decimal,
        expected_profile: RiskProfile,
    ) -> None:
        subgraph = build_risk_subgraph()
        state = _base_state(annual_income=annual_income, debt_utilization=debt_utilization)
        result = subgraph.invoke(state)
        assert result["risk_response"].risk_profile == expected_profile

    def test_deterministic_same_input_same_output(self) -> None:
        """Same input must produce identical output across multiple invocations."""
        subgraph = build_risk_subgraph()
        state = _base_state(annual_income=Decimal("90000"), debt_utilization=Decimal("0.20"))
        result_a = subgraph.invoke(dict(state))
        result_b = subgraph.invoke(dict(state))
        assert result_a["risk_response"].credit_score == result_b["risk_response"].credit_score
        assert result_a["risk_response"].risk_profile == result_b["risk_response"].risk_profile
