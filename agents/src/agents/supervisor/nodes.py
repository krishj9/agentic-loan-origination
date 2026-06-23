"""Pure-function node implementations for the supervisor graph (P3-T2, P3-T8).

Every function in this module is a *pure node*: it takes a
``LoanApplicationState`` dict and returns a partial dict of state updates.
Nodes have no side effects — they do not mutate the state argument, call
non-deterministic external services directly, or hold module-level mutable
state.  All I/O is delegated to the specialist subgraphs or tool callables.

Node sequence (design §5.1):
    ingest_application → validate_inputs → process_documents → run_risk
    → run_compliance → make_decision → package_artifacts → persist_and_publish

Terminal nodes (conditional branches, P3-T3):
    error_terminal         — missing/invalid docs or unrecoverable failure
    manual_review_terminal — REFER decision routed to human review

Decision logic (P3-T8):
    make_decision combines risk band + compliance action using explicit rules;
    rationale is assembled from engine-provided explanations only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.schemas import (
    ApplicationStatus,
    ComplianceAction,
    Decision,
    DecisionOutcome,
    DocumentType,
    RiskProfile,
)

from agents.log import get_logger
from agents.state import LoanApplicationState

log = get_logger(__name__)

# ── Thresholds ───────────────────────────────────────────────────────────────

_MAX_PARSE_FAILURES_BEFORE_REFER = 1
_EXTREME_SUBPRIME_MIN_FLAGS = 2  # Both HIGH_UTILIZATION and LOW_INCOME → early decline


# ── Node 1: ingest_application ───────────────────────────────────────────────

def ingest_application(state: LoanApplicationState) -> dict[str, Any]:
    """Validate core identifiers are present and mark the application as PROCESSING.

    This is the first node in the graph.  It does not perform I/O; it
    ensures the state carries the minimum required fields before any
    downstream work begins.
    """
    application_id = state.get("application_id", "")
    user_id = state.get("user_id", "")
    application = state.get("application")

    if not application_id or not user_id:
        log.warning(
            "supervisor.ingest_application.missing_identifiers",
            extra={"application_id": application_id, "user_id": user_id},
        )
        return {"error": "Missing required identifiers: application_id and user_id must be set."}

    submitted_at = state.get("submitted_at") or datetime.now(UTC)
    updates: dict[str, Any] = {
        "submitted_at": submitted_at,
        "parse_failure_count": state.get("parse_failure_count", 0),
        "needs_manual_review": False,
    }

    if application is not None:
        updated_app = application.model_copy(update={"status": ApplicationStatus.PROCESSING})
        updates["application"] = updated_app

    log.info(
        "supervisor.ingest_application",
        extra={
            "application_id": application_id,
            "user_id": user_id,
            "trace_id": state.get("trace_id"),
            "runtime_session_id": state.get("runtime_session_id"),
        },
    )
    return updates


# ── Node 2: validate_inputs ──────────────────────────────────────────────────

def validate_inputs(state: LoanApplicationState) -> dict[str, Any]:
    """Check that the document inventory contains the required document types.

    Required types: PAYSTUB and BANK_STATEMENT (design §12.1).
    Returns an ``error`` key when validation fails so the conditional edge
    can route to the error terminal (P3-T3).
    """
    application_id = state.get("application_id", "unknown")
    inventory = state.get("document_inventory", [])

    present_types = {doc.document_type for doc in inventory}
    required_types = {DocumentType.PAYSTUB, DocumentType.BANK_STATEMENT}
    missing = required_types - present_types

    if missing:
        missing_labels = ", ".join(sorted(t.value for t in missing))
        error_msg = f"Missing required document types: {missing_labels}."
        log.warning(
            "supervisor.validate_inputs.missing_documents",
            extra={
                "application_id": application_id,
                "missing_types": sorted(t.value for t in missing),
                "trace_id": state.get("trace_id"),
            },
        )
        return {"error": error_msg}

    log.info(
        "supervisor.validate_inputs.passed",
        extra={
            "application_id": application_id,
            "document_types": [t.value for t in present_types],
            "trace_id": state.get("trace_id"),
        },
    )
    return {}


# ── Node 3: process_documents ────────────────────────────────────────────────

def process_documents(state: LoanApplicationState) -> dict[str, Any]:
    """Invoke the document-extraction subgraph and merge results into state."""
    from agents.subgraphs.document import build_document_subgraph

    application_id = state.get("application_id", "unknown")
    log.info(
        "supervisor.process_documents.start",
        extra={"application_id": application_id, "trace_id": state.get("trace_id")},
    )
    subgraph = build_document_subgraph()
    result: dict[str, Any] = subgraph.invoke(dict(state))

    return {
        "document_inventory": result.get("document_inventory", state.get("document_inventory", [])),
        "pay_stub_data": result.get("pay_stub_data"),
        "bank_statement_data": result.get("bank_statement_data"),
        "parse_failure_count": result.get("parse_failure_count", state.get("parse_failure_count", 0)),
    }


# ── Node 4: run_risk ─────────────────────────────────────────────────────────

def run_risk(state: LoanApplicationState) -> dict[str, Any]:
    """Invoke the risk subgraph and store the RiskResponse in state."""
    from agents.subgraphs.risk import build_risk_subgraph

    application_id = state.get("application_id", "unknown")
    log.info(
        "supervisor.run_risk.start",
        extra={"application_id": application_id, "trace_id": state.get("trace_id")},
    )
    subgraph = build_risk_subgraph()
    result: dict[str, Any] = subgraph.invoke(dict(state))

    return {
        "risk_request": result.get("risk_request"),
        "risk_response": result.get("risk_response"),
    }


# ── Node 5: run_compliance ────────────────────────────────────────────────────

def run_compliance(state: LoanApplicationState) -> dict[str, Any]:
    """Invoke the compliance subgraph and store the ComplianceResult in state."""
    from agents.subgraphs.compliance import build_compliance_subgraph

    application_id = state.get("application_id", "unknown")
    log.info(
        "supervisor.run_compliance.start",
        extra={"application_id": application_id, "trace_id": state.get("trace_id")},
    )
    subgraph = build_compliance_subgraph()
    result: dict[str, Any] = subgraph.invoke(dict(state))

    return {"compliance_result": result.get("compliance_result")}


# ── Node 6: make_decision (P3-T8) ────────────────────────────────────────────

def make_decision(state: LoanApplicationState) -> dict[str, Any]:
    """Derive the final underwriting decision from risk band + compliance action.

    Decision rules (explicit, deterministic — no LLM involvement):
    1. If compliance recommended DECLINE  → outcome = DECLINE
    2. If risk profile is SUBPRIME and compliance recommended REFER → outcome = DECLINE
    3. If compliance recommended REFER    → outcome = REFER
    4. If risk profile is SUBPRIME        → outcome = REFER (conservative)
    5. If parse_failure_count exceeded threshold → outcome = REFER (data quality)
    6. Otherwise                          → outcome = APPROVE

    Rationale is assembled exclusively from engine-provided explanations
    (``score_range_rationale`` + triggered compliance flags).
    """
    application_id = state.get("application_id", "unknown")
    risk_response = state.get("risk_response")
    compliance_result = state.get("compliance_result")
    parse_failures = state.get("parse_failure_count", 0)

    # Determine outcome
    if parse_failures > _MAX_PARSE_FAILURES_BEFORE_REFER:
        outcome = DecisionOutcome.REFER
        rationale = (
            f"Document parsing failed {parse_failures} time(s). "
            "Application referred for manual review due to data quality issues."
        )
        risk_profile = risk_response.risk_profile if risk_response else RiskProfile.SUBPRIME
        credit_score = risk_response.credit_score if risk_response else 0
    elif risk_response is None or compliance_result is None:
        outcome = DecisionOutcome.DECLINE
        rationale = "Insufficient data: risk evaluation or compliance check did not complete."
        risk_profile = RiskProfile.SUBPRIME
        credit_score = 0
    else:
        risk_profile = risk_response.risk_profile
        credit_score = risk_response.credit_score
        compliance_action = compliance_result.recommended_action
        triggered_flags = [f for f in compliance_result.flags if f.triggered]

        if compliance_action == ComplianceAction.DECLINE:
            outcome = DecisionOutcome.DECLINE
        elif risk_profile == RiskProfile.SUBPRIME and compliance_action == ComplianceAction.REFER:
            outcome = DecisionOutcome.DECLINE
        elif compliance_action == ComplianceAction.REFER:
            outcome = DecisionOutcome.REFER
        elif risk_profile == RiskProfile.SUBPRIME:
            outcome = DecisionOutcome.REFER
        else:
            outcome = DecisionOutcome.APPROVE

        # Build rationale from engine explanations only
        parts: list[str] = [risk_response.score_range_rationale]
        if triggered_flags:
            flag_descs = "; ".join(f.description for f in triggered_flags)
            parts.append(f"Compliance flags: {flag_descs}")
        else:
            parts.append("No compliance flags triggered.")
        rationale = " ".join(parts)

    decided_at = datetime.now(UTC)
    decision = Decision(
        application_id=application_id,
        outcome=outcome,
        risk_profile=risk_profile,
        credit_score=credit_score,
        rationale=rationale,
        risk_response=risk_response,
        compliance_result=compliance_result,
    )

    log.info(
        "supervisor.make_decision",
        extra={
            "application_id": application_id,
            "outcome": outcome,
            "risk_profile": risk_profile,
            "credit_score": credit_score,
            "trace_id": state.get("trace_id"),
        },
    )
    return {
        "decision": decision,
        "decided_at": decided_at,
        "needs_manual_review": outcome == DecisionOutcome.REFER,
    }


# ── Node 7: package_artifacts ─────────────────────────────────────────────────

def package_artifacts(state: LoanApplicationState) -> dict[str, Any]:
    """Invoke the packaging subgraph to produce JSON + PDF artifacts."""
    from agents.subgraphs.packaging import build_packaging_subgraph

    application_id = state.get("application_id", "unknown")
    log.info(
        "supervisor.package_artifacts.start",
        extra={"application_id": application_id, "trace_id": state.get("trace_id")},
    )
    subgraph = build_packaging_subgraph()
    result: dict[str, Any] = subgraph.invoke(dict(state))

    return {
        "audit_context": result.get("audit_context"),
        "artifact_json_s3_key": result.get("artifact_json_s3_key"),
        "artifact_pdf_s3_key": result.get("artifact_pdf_s3_key"),
    }


# ── Node 8: persist_and_publish ───────────────────────────────────────────────

def persist_and_publish(state: LoanApplicationState) -> dict[str, Any]:
    """Finalize the application status and emit the completion log event.

    In production this node also publishes an EventBridge / SNS event to
    notify downstream consumers (Phase 4 / enterprise backlog).  For Phase 3
    it updates the application status and logs the final structured record.
    """
    application_id = state.get("application_id", "unknown")
    decision = state.get("decision")
    application = state.get("application")

    outcome = decision.outcome if decision else "UNKNOWN"
    new_status = ApplicationStatus.COMPLETED if decision else ApplicationStatus.FAILED

    updates: dict[str, Any] = {}
    if application is not None:
        updates["application"] = application.model_copy(update={"status": new_status})

    log.info(
        "supervisor.persist_and_publish.complete",
        extra={
            "application_id": application_id,
            "decision_outcome": outcome,
            "artifact_json_s3_key": state.get("artifact_json_s3_key"),
            "artifact_pdf_s3_key": state.get("artifact_pdf_s3_key"),
            "runtime_session_id": state.get("runtime_session_id"),
            "trace_id": state.get("trace_id"),
        },
    )
    return updates


# ── Terminal nodes (P3-T3) ────────────────────────────────────────────────────

def error_terminal(state: LoanApplicationState) -> dict[str, Any]:
    """Terminal node for unrecoverable failures (missing docs, invalid input).

    Sets application status to FAILED and logs the structured error event.
    """
    application_id = state.get("application_id", "unknown")
    error = state.get("error", "Unknown error")
    application = state.get("application")

    log.warning(
        "supervisor.error_terminal",
        extra={
            "application_id": application_id,
            "error": error,
            "trace_id": state.get("trace_id"),
        },
    )
    updates: dict[str, Any] = {}
    if application is not None:
        updates["application"] = application.model_copy(update={"status": ApplicationStatus.FAILED})
    return updates


def manual_review_terminal(state: LoanApplicationState) -> dict[str, Any]:
    """Terminal node for REFER decisions requiring human review.

    Sets application status to MANUAL_REVIEW and emits a structured log
    event that can trigger a downstream review-queue notification.
    """
    application_id = state.get("application_id", "unknown")
    decision = state.get("decision")
    application = state.get("application")

    log.info(
        "supervisor.manual_review_terminal",
        extra={
            "application_id": application_id,
            "risk_profile": decision.risk_profile if decision else None,
            "credit_score": decision.credit_score if decision else None,
            "trace_id": state.get("trace_id"),
        },
    )
    updates: dict[str, Any] = {}
    if application is not None:
        updates["application"] = application.model_copy(
            update={"status": ApplicationStatus.MANUAL_REVIEW}
        )
    return updates
