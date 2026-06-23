"""Unit tests for the packaging specialist subgraph (P3-T7, P3-T12).

Tests cover:
* build_audit_context assembles AuditContext from state fields
* generate_artifacts produces deterministic S3 key paths
* Artifacts follow archive/{application_id}/ prefix convention
* Missing decision or audit_context returns empty dict without error
* Subgraph end-to-end compilation and invocation
"""

from __future__ import annotations

from datetime import UTC, datetime

from agents.subgraphs.packaging import (
    build_audit_context,
    build_packaging_subgraph,
    generate_artifacts,
)
from shared.schemas import (
    Decision,
    DecisionOutcome,
    RiskProfile,
)


def _make_decision(application_id: str = "app_pkg_001") -> Decision:
    return Decision(
        applicationId=application_id,
        outcome=DecisionOutcome.APPROVE,
        riskProfile=RiskProfile.PRIME,
        creditScore=745,
        rationale="Income band HIGH, utilization band LOW. No compliance flags triggered.",
    )


def _make_base_state(application_id: str = "app_pkg_001") -> dict:
    return {
        "application_id": application_id,
        "user_id": "user_test",
        "trace_id": "trace_pkg_001",
        "runtime_session_id": "session_xyz",
        "decision": _make_decision(application_id),
        "audit_context": None,
        "submitted_at": datetime(2026, 6, 22, 18, 0, 0, tzinfo=UTC),
        "decided_at": datetime(2026, 6, 22, 18, 0, 45, tzinfo=UTC),
    }


class TestBuildAuditContextNode:
    def test_audit_context_populated(self) -> None:
        state = _make_base_state()
        result = build_audit_context(state)
        ctx = result["audit_context"]
        assert ctx.application_id == "app_pkg_001"
        assert ctx.user_id == "user_test"
        assert ctx.trace_id == "trace_pkg_001"
        assert ctx.runtime_session_id == "session_xyz"

    def test_submission_timestamp_set(self) -> None:
        state = _make_base_state()
        result = build_audit_context(state)
        assert result["audit_context"].submission_timestamp is not None

    def test_decision_timestamp_set_from_state(self) -> None:
        state = _make_base_state()
        result = build_audit_context(state)
        ctx = result["audit_context"]
        expected_ts = datetime(2026, 6, 22, 18, 0, 45, tzinfo=UTC)
        assert ctx.decision_timestamp == expected_ts


class TestGenerateArtifactsNode:
    def _state_with_audit_context(self, application_id: str = "app_pkg_001") -> dict:
        state = _make_base_state(application_id)
        audit_result = build_audit_context(state)
        return {**state, **audit_result}

    def test_json_s3_key_follows_prefix_convention(self) -> None:
        state = self._state_with_audit_context("app_pkg_999")
        result = generate_artifacts(state)
        assert result["artifact_json_s3_key"].startswith("archive/app_pkg_999/")
        assert result["artifact_json_s3_key"].endswith(".json")

    def test_pdf_s3_key_follows_prefix_convention(self) -> None:
        state = self._state_with_audit_context("app_pkg_999")
        result = generate_artifacts(state)
        assert result["artifact_pdf_s3_key"].startswith("archive/app_pkg_999/")
        assert result["artifact_pdf_s3_key"].endswith(".pdf")

    def test_missing_decision_returns_empty(self) -> None:
        state = self._state_with_audit_context()
        state["decision"] = None
        result = generate_artifacts(state)
        assert result == {}

    def test_missing_audit_context_returns_empty(self) -> None:
        state = _make_base_state()
        state["audit_context"] = None
        result = generate_artifacts(state)
        assert result == {}


class TestPackagingSubgraphEndToEnd:
    def test_compiles(self) -> None:
        assert build_packaging_subgraph() is not None

    def test_end_to_end_produces_s3_keys(self) -> None:
        subgraph = build_packaging_subgraph()
        state = _make_base_state("app_pkg_e2e")
        result = subgraph.invoke(state)
        assert result.get("artifact_json_s3_key", "").startswith("archive/app_pkg_e2e/")
        assert result.get("artifact_pdf_s3_key", "").startswith("archive/app_pkg_e2e/")

    def test_audit_context_written_to_state(self) -> None:
        subgraph = build_packaging_subgraph()
        state = _make_base_state()
        result = subgraph.invoke(state)
        assert result.get("audit_context") is not None
        assert result["audit_context"].application_id == "app_pkg_001"
