"""Packaging specialist subgraph (P3-T7).

Implements the artifact-generation pipeline described in design §5.3 / §9:

    build_audit_context  →  generate_artifacts

* ``build_audit_context`` — assembles the ``AuditContext`` envelope from
                            the current pipeline state (design §4.4).
* ``generate_artifacts``  — calls ``packaging.generate_artifacts`` to produce
                            a machine-readable decision JSON + human-readable PDF
                            and records the S3 artifact keys in state.

Neither node modifies the ``Decision`` object; they only enrich state with
audit metadata and persist artifact keys.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from shared.schemas import AuditContext

from agents.log import get_logger
from agents.state import LoanApplicationState
from agents.tools.packaging_tool import PackagingToolRequest, call_packaging

log = get_logger(__name__)


# ── Node: build_audit_context ────────────────────────────────────────────────

def build_audit_context(state: LoanApplicationState) -> dict[str, Any]:
    """Assemble the immutable audit envelope for S3 archive artifacts.

    Collects all required audit fields from state (design §4.4):
        application_id, user_id, submission_timestamp, decision_timestamp,
        runtime_session_id, trace_id.
    """
    application_id = state.get("application_id", "unknown")
    submitted_at = state.get("submitted_at") or datetime.now(UTC)
    decided_at = state.get("decided_at") or datetime.now(UTC)

    audit_context = AuditContext(
        application_id=application_id,
        user_id=state.get("user_id", "unknown"),
        submission_timestamp=submitted_at,
        decision_timestamp=decided_at,
        runtime_session_id=state.get("runtime_session_id"),
        trace_id=state.get("trace_id"),
    )
    log.info(
        "packaging_subgraph.build_audit_context",
        extra={
            "application_id": application_id,
            "trace_id": state.get("trace_id"),
        },
    )
    return {"audit_context": audit_context}


# ── Node: generate_artifacts ─────────────────────────────────────────────────

def generate_artifacts(state: LoanApplicationState) -> dict[str, Any]:
    """Generate JSON + PDF decision artifacts and record their S3 keys.

    Calls ``packaging.generate_artifacts`` with the finalized decision and
    audit context.  The stub writes in-memory; the Phase 4 implementation
    performs the actual TLS-encrypted, KMS-encrypted S3 upload.
    """
    application_id = state.get("application_id", "unknown")
    decision = state.get("decision")
    audit_context = state.get("audit_context")

    if decision is None or audit_context is None:
        log.warning(
            "packaging_subgraph.generate_artifacts.missing_inputs",
            extra={
                "application_id": application_id,
                "has_decision": decision is not None,
                "has_audit_context": audit_context is not None,
            },
        )
        return {}

    s3_bucket = os.environ.get("S3_BUCKET_NAME", "loan-origination-documents-demo")
    request = PackagingToolRequest(
        application_id=application_id,
        decision=decision,
        audit_context=audit_context,
        s3_bucket=s3_bucket,
    )
    response = call_packaging(request)

    log.info(
        "packaging_subgraph.generate_artifacts.complete",
        extra={
            "application_id": application_id,
            "artifact_json_s3_key": response.artifact_json_s3_key,
            "artifact_pdf_s3_key": response.artifact_pdf_s3_key,
            "trace_id": state.get("trace_id"),
        },
    )
    return {
        "artifact_json_s3_key": response.artifact_json_s3_key,
        "artifact_pdf_s3_key": response.artifact_pdf_s3_key,
    }


# ── Subgraph factory ────────────────────────────────────────────────────────

def build_packaging_subgraph() -> CompiledStateGraph:
    """Compile and return the packaging LangGraph subgraph."""
    graph: StateGraph = StateGraph(LoanApplicationState)
    graph.add_node("build_audit_context", build_audit_context)
    graph.add_node("generate_artifacts", generate_artifacts)

    graph.add_edge(START, "build_audit_context")
    graph.add_edge("build_audit_context", "generate_artifacts")
    graph.add_edge("generate_artifacts", END)

    return graph.compile()
