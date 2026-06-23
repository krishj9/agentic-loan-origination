"""Unit tests for the shared LangGraph state model (P3-T1, P3-T12)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from agents.state import LoanApplicationState
from shared.schemas import ApplicationStatus, CanonicalApplication


def _make_base_state() -> LoanApplicationState:
    """Return a minimal valid state dict for testing."""
    return {
        "application_id": "app_test_001",
        "user_id": "user_abc",
        "trace_id": "trace_xyz",
        "runtime_session_id": None,
        "application": None,
        "document_inventory": [],
        "pay_stub_data": None,
        "bank_statement_data": None,
        "risk_request": None,
        "risk_response": None,
        "compliance_result": None,
        "decision": None,
        "artifact_json_s3_key": None,
        "artifact_pdf_s3_key": None,
        "audit_context": None,
        "error": None,
        "needs_manual_review": False,
        "parse_failure_count": 0,
        "submitted_at": None,
        "decided_at": None,
    }


class TestLoanApplicationStateStructure:
    """Verify state is a plain dict at runtime with expected keys."""

    def test_state_is_dict(self) -> None:
        state = _make_base_state()
        assert isinstance(state, dict)

    def test_required_identifiers_present(self) -> None:
        state = _make_base_state()
        assert state["application_id"] == "app_test_001"
        assert state["user_id"] == "user_abc"
        assert state["trace_id"] == "trace_xyz"

    def test_all_expected_keys(self) -> None:
        state = _make_base_state()
        expected_keys = {
            "application_id",
            "user_id",
            "trace_id",
            "runtime_session_id",
            "application",
            "document_inventory",
            "pay_stub_data",
            "bank_statement_data",
            "risk_request",
            "risk_response",
            "compliance_result",
            "decision",
            "artifact_json_s3_key",
            "artifact_pdf_s3_key",
            "audit_context",
            "error",
            "needs_manual_review",
            "parse_failure_count",
            "submitted_at",
            "decided_at",
        }
        assert expected_keys.issubset(set(state.keys()))


class TestStateWithCanonicalApplication:
    """Verify state round-trips Pydantic models correctly."""

    def test_canonical_application_stored_in_state(self) -> None:
        app = CanonicalApplication(
            applicationId="app_test_001",
            userId="user_abc",
            applicantName="Jane Smith",
            annualIncome=Decimal("85000.00"),
            requestedLoanAmount=Decimal("20000.00"),
            debtUtilization=Decimal("0.25"),
            status=ApplicationStatus.PENDING,
        )
        state = _make_base_state()
        state["application"] = app

        assert state["application"].application_id == "app_test_001"
        assert state["application"].annual_income == Decimal("85000.00")
        assert state["application"].status == ApplicationStatus.PENDING

    def test_partial_state_update_merge(self) -> None:
        """Verify that partial dict merging (simulated) preserves existing fields."""
        state = _make_base_state()
        update: LoanApplicationState = {"error": "test_error"}  # type: ignore[typeddict-item]

        merged = {**state, **update}
        assert merged["error"] == "test_error"
        assert merged["application_id"] == "app_test_001"

    def test_timestamp_fields_accept_datetime(self) -> None:
        state = _make_base_state()
        now = datetime.now(UTC)
        state["submitted_at"] = now
        state["decided_at"] = now
        assert state["submitted_at"] == now
        assert state["decided_at"] == now
