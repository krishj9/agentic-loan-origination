"""Shared LangGraph state for the loan origination supervisor (P3-T1).

The single TypedDict that flows through the entire supervisor graph and all
specialist subgraphs.  All nested domain objects are Pydantic v2 models
imported from shared.schemas (design §5.2).

State is never mutated in place.  Nodes return partial dicts; LangGraph
merges them using last-write-wins semantics, preserving functional node
purity (design §5.1).  Use ``state.get("key")`` inside node functions to
safely read optional fields that may not yet be populated.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from shared.schemas import (
    AuditContext,
    BankStatementFields,
    CanonicalApplication,
    ComplianceResult,
    Decision,
    Document,
    PayStubFields,
    RiskRequest,
    RiskResponse,
)


class LoanApplicationState(TypedDict, total=False):
    """Shared state object for one loan-application pipeline run.

    Fields are populated incrementally as the graph progresses:

    * ``ingest_application`` sets core identifiers and ``application``.
    * ``validate_inputs``   validates document inventory; sets ``error`` on failure.
    * ``process_documents`` subgraph sets ``pay_stub_data`` / ``bank_statement_data``.
    * ``run_risk``           subgraph sets ``risk_request`` / ``risk_response``.
    * ``run_compliance``     subgraph sets ``compliance_result``.
    * ``make_decision``      sets ``decision`` and ``decided_at``.
    * ``package_artifacts``  subgraph sets ``artifact_json_s3_key`` / ``artifact_pdf_s3_key``.
    * ``persist_and_publish`` sets ``audit_context`` before final persistence.
    """

    # ── Core identifiers (always present after ingest_application) ──────────
    application_id: str
    user_id: str
    trace_id: str
    runtime_session_id: str | None

    # ── Top-level application record ────────────────────────────────────────
    application: CanonicalApplication | None

    # ── Document inventory (S3 keys + parse-lifecycle status) ───────────────
    document_inventory: list[Document]

    # ── Normalized financial data (post document-extraction subgraph) ────────
    pay_stub_data: PayStubFields | None
    bank_statement_data: BankStatementFields | None

    # ── Risk engine inputs / outputs (post risk subgraph) ───────────────────
    risk_request: RiskRequest | None
    risk_response: RiskResponse | None

    # ── Compliance evaluation result (post compliance subgraph) ─────────────
    compliance_result: ComplianceResult | None

    # ── Final decision (post make_decision node) ─────────────────────────────
    decision: Decision | None

    # ── S3 artifact references (post package_artifacts subgraph) ────────────
    artifact_json_s3_key: str | None
    artifact_pdf_s3_key: str | None

    # ── Audit envelope (assembled before persist_and_publish) ────────────────
    audit_context: AuditContext | None

    # ── Control-flow bookkeeping ─────────────────────────────────────────────
    error: str | None           # Structured error description for terminal failures
    needs_manual_review: bool      # True when a REFER decision routes to the manual-review terminal
    parse_failure_count: int       # Incremented on parse failures; triggers retry-then-refer logic

    # ── Pipeline timestamps (UTC) ────────────────────────────────────────────
    submitted_at: datetime | None
    decided_at: datetime | None

    # ── Internal / transient fields (not persisted to S3 archive) ───────────
    # Intermediate LlamaParse responses carried between parse_documents and
    # normalize_documents nodes within the document-extraction subgraph only.
    # Typed as list[Any] to avoid importing tool-layer types into the state module.
    _parse_results: list | None
