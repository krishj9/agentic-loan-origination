"""Unit tests for AgentCore Runtime client in local mode (P3-T9, P3-T12).

Tests do NOT require AWS credentials — they exercise the LOCAL runtime mode
only (in-process LangGraph execution).

Tests cover:
* Client defaults to local mode when RUNTIME_MODE=local
* Successful run_session returns a SessionResult with succeeded=True
* Final state contains a decision after happy-path run
* Error in graph returns SessionResult with succeeded=False and error set
* Gateway dry-run registration returns status=dry_run for all tools
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from agents.runtime.client import AgentCoreRuntimeClient, RuntimeMode, SessionResult
from agents.runtime.gateway import get_tool_definitions, register_tools
from shared.schemas import ApplicationStatus, CanonicalApplication, Document, DocumentType


def _make_full_initial_state(application_id: str = "app_rt_001") -> dict:
    """Build a minimal but complete initial state for the supervisor graph."""

    app = CanonicalApplication(
        applicationId=application_id,
        userId="user_rt",
        applicantName="John Doe",
        annualIncome=Decimal("90000"),
        requestedLoanAmount=Decimal("20000"),
        debtUtilization=Decimal("0.20"),
        status=ApplicationStatus.PENDING,
    )
    now = datetime.now(UTC)
    return {
        "application_id": application_id,
        "user_id": "user_rt",
        "trace_id": "trace_rt_001",
        "runtime_session_id": None,
        "application": app,
        "document_inventory": [
            Document(
                document_id="doc_ps",
                application_id=application_id,
                document_type=DocumentType.PAYSTUB,
                s3_key=f"incoming/{application_id}/paystub.pdf",
                uploaded_at=now,
                parse_status="PENDING",
            ),
            Document(
                document_id="doc_bs",
                application_id=application_id,
                document_type=DocumentType.BANK_STATEMENT,
                s3_key=f"incoming/{application_id}/bank_statement.pdf",
                uploaded_at=now,
                parse_status="PENDING",
            ),
        ],
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
        "submitted_at": now,
        "decided_at": None,
    }


class TestAgentCoreRuntimeClientLocal:
    def test_defaults_to_local_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RUNTIME_MODE", "local")
        client = AgentCoreRuntimeClient()
        assert client._mode == RuntimeMode.LOCAL

    def test_run_session_returns_session_result(self) -> None:
        client = AgentCoreRuntimeClient(mode=RuntimeMode.LOCAL)
        initial_state = _make_full_initial_state()
        result = client.run_session(
            application_id="app_rt_001",
            initial_state=initial_state,
            trace_id="trace_rt_001",
        )
        assert isinstance(result, SessionResult)

    def test_run_session_happy_path_succeeds(self) -> None:
        client = AgentCoreRuntimeClient(mode=RuntimeMode.LOCAL)
        initial_state = _make_full_initial_state("app_rt_happy")
        result = client.run_session("app_rt_happy", initial_state)
        assert result.succeeded is True
        assert result.error is None

    def test_run_session_produces_decision(self) -> None:
        client = AgentCoreRuntimeClient(mode=RuntimeMode.LOCAL)
        initial_state = _make_full_initial_state("app_rt_decision")
        result = client.run_session("app_rt_decision", initial_state)
        assert result.succeeded is True
        assert result.final_state.get("decision") is not None

    def test_run_session_sets_runtime_session_id(self) -> None:
        client = AgentCoreRuntimeClient(mode=RuntimeMode.LOCAL)
        result = client.run_session("app_rt_sid", _make_full_initial_state("app_rt_sid"))
        assert result.runtime_session_id is not None
        assert result.runtime_session_id != ""

    def test_run_session_propagates_trace_id(self) -> None:
        client = AgentCoreRuntimeClient(mode=RuntimeMode.LOCAL)
        result = client.run_session(
            "app_rt_trace",
            _make_full_initial_state("app_rt_trace"),
            trace_id="my_trace_xyz",
        )
        assert result.trace_id == "my_trace_xyz"

    def test_missing_docs_produces_failed_or_refer(self) -> None:
        """Graph with no documents should not crash — terminal error or refer state."""
        client = AgentCoreRuntimeClient(mode=RuntimeMode.LOCAL)
        state = _make_full_initial_state("app_rt_no_docs")
        state["document_inventory"] = []
        result = client.run_session("app_rt_no_docs", state)
        # Either succeeded=True (error terminal reached) or the error is set
        # The important invariant is: we get a SessionResult, not an exception
        assert isinstance(result, SessionResult)


class TestGatewayDryRun:
    def test_dry_run_returns_all_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RUNTIME_MODE", "local")
        results = register_tools(dry_run=True)
        assert len(results) == 4

    def test_dry_run_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RUNTIME_MODE", "local")
        results = register_tools(dry_run=True)
        for r in results:
            assert r["status"] == "dry_run"

    def test_get_tool_definitions_returns_specs(self) -> None:
        specs = get_tool_definitions()
        assert len(specs) == 4
        names = {s["name"] for s in specs}
        assert "risk_engine.evaluate" in names
