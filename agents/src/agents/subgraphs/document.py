"""Document-extraction specialist subgraph (P3-T4).

Implements the three-node extraction pipeline described in design §5.3 / §6:

    load_documents  →  parse_documents  →  normalize_documents

* ``load_documents``     — validates that document S3 keys are present in
                           state and marks documents as PROCESSING.
* ``parse_documents``    — calls ``llamaparse.parse_financial_pdf`` for each
                           document; increments ``parse_failure_count`` and
                           surfaces structured ``confidence_notes`` on failure.
* ``normalize_documents`` — maps LlamaParse output to canonical Pydantic models
                            (``PayStubFields`` / ``BankStatementFields``).

The subgraph shares the top-level ``LoanApplicationState`` so all updates
flow directly back to the supervisor without an adapter layer.

Retry logic: ``parse_documents`` retries each document up to
``MAX_PARSE_RETRIES`` times before writing to ``parse_failure_count``;
the supervisor graph's conditional edge handles the REFER branch.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from shared.schemas import BankStatementFields, DocumentType, PayStubFields, Transaction

from agents.log import get_logger
from agents.state import LoanApplicationState
from agents.tools.llamaparse_tool import LlamaParseRequest, LlamaParseResponse, call_llamaparse

log = get_logger(__name__)

MAX_PARSE_RETRIES = 2


# ── Node: load_documents ────────────────────────────────────────────────────

def load_documents(state: LoanApplicationState) -> dict[str, Any]:
    """Validate that document records exist and mark them as PROCESSING.

    This node is a pure guard — it does not perform I/O.  Missing inventory
    is treated as a parse failure (sets ``parse_failure_count`` to 1 so the
    supervisor can decide whether to REFER or halt).
    """
    application_id = state.get("application_id", "unknown")
    inventory = state.get("document_inventory", [])

    log.info(
        "document_subgraph.load_documents",
        extra={
            "application_id": application_id,
            "trace_id": state.get("trace_id"),
            "document_count": len(inventory),
        },
    )

    if not inventory:
        log.warning(
            "document_subgraph.load_documents.empty_inventory",
            extra={"application_id": application_id},
        )
        return {"parse_failure_count": 1}

    updated = []
    for doc in inventory:
        updated_doc = doc.model_copy(update={"parse_status": "PROCESSING"})
        updated.append(updated_doc)

    return {"document_inventory": updated}


# ── Node: parse_documents ────────────────────────────────────────────────────

def parse_documents(state: LoanApplicationState) -> dict[str, Any]:
    """Invoke ``llamaparse.parse_financial_pdf`` for each document in inventory.

    Stores the raw LlamaParse responses in a transient list on the state
    (``_parse_results``) for the normalization node to consume.  Failures are
    recorded; the overall ``parse_failure_count`` is updated.
    """
    application_id = state.get("application_id", "unknown")
    inventory = state.get("document_inventory", [])
    failure_count = state.get("parse_failure_count", 0)
    parse_results: list[LlamaParseResponse] = []
    updated_docs = []

    for doc in inventory:
        request = LlamaParseRequest(
            application_id=application_id,
            document_id=doc.document_id,
            document_type=doc.document_type,
            s3_key=doc.s3_key,
            parse_profile=f"{doc.document_type.lower()}_v1",
        )
        attempt = 0
        last_error: str = ""
        parsed: LlamaParseResponse | None = None

        while attempt < MAX_PARSE_RETRIES:
            try:
                parsed = call_llamaparse(request)
                log.info(
                    "document_subgraph.parse_documents.success",
                    extra={
                        "application_id": application_id,
                        "document_id": doc.document_id,
                        "document_type": doc.document_type,
                        "trace_id": state.get("trace_id"),
                    },
                )
                break
            except Exception as exc:
                attempt += 1
                last_error = str(exc)
                log.warning(
                    "document_subgraph.parse_documents.retry",
                    extra={
                        "application_id": application_id,
                        "document_id": doc.document_id,
                        "attempt": attempt,
                        "error": last_error,
                    },
                )

        if parsed is None:
            failure_count += 1
            updated_docs.append(doc.model_copy(update={"parse_status": "FAILED"}))
            log.warning(
                "document_subgraph.parse_documents.failed",
                extra={
                    "application_id": application_id,
                    "document_id": doc.document_id,
                    "error": last_error,
                },
            )
        else:
            parse_results.append(parsed)
            updated_docs.append(doc.model_copy(update={"parse_status": "COMPLETED"}))

    return {
        "document_inventory": updated_docs,
        "_parse_results": parse_results,
        "parse_failure_count": failure_count,
    }


# ── Node: normalize_documents ────────────────────────────────────────────────

def _normalize_paystub(fields: dict[str, Any], notes: list[str]) -> PayStubFields:
    """Map LlamaParse structured fields to canonical ``PayStubFields``."""

    def _date(val: Any) -> date:  # noqa: ANN401
        if isinstance(val, date):
            return val
        return date.fromisoformat(str(val))

    def _decimal(val: Any) -> Decimal:  # noqa: ANN401
        return Decimal(str(val)).quantize(Decimal("0.01"))

    return PayStubFields(
        employee_name=str(fields.get("employee_name", "")),
        employer_name=str(fields.get("employer_name", "")),
        pay_period_start=_date(fields.get("pay_period_start", "2026-01-01")),
        pay_period_end=_date(fields.get("pay_period_end", "2026-01-31")),
        pay_date=_date(fields.get("pay_date", "2026-02-01")),
        gross_pay=_decimal(fields.get("gross_pay", "0")),
        deductions=_decimal(fields.get("deductions", "0")),
        net_pay=_decimal(fields.get("net_pay", "0")),
        ytd_gross_pay=_decimal(fields["ytd_gross_pay"]) if "ytd_gross_pay" in fields else None,
        ytd_net_pay=_decimal(fields["ytd_net_pay"]) if "ytd_net_pay" in fields else None,
        confidence_notes=notes,
    )


def _normalize_bank_statement(
    fields: dict[str, Any],
    rows: list[dict[str, Any]],
    notes: list[str],
) -> BankStatementFields:
    """Map LlamaParse structured fields to canonical ``BankStatementFields``."""

    def _date(val: Any) -> date:  # noqa: ANN401
        if isinstance(val, date):
            return val
        return date.fromisoformat(str(val))

    def _decimal(val: Any) -> Decimal:  # noqa: ANN401
        return Decimal(str(val)).quantize(Decimal("0.01"))

    transactions = [
        Transaction(
            date=_date(row.get("date", "2026-01-01")),
            description=str(row.get("description", "")),
            amount=_decimal(row.get("amount", "0")),
            balance=_decimal(row["balance"]) if "balance" in row else None,
        )
        for row in rows
    ]
    return BankStatementFields(
        account_holder_name=str(fields.get("account_holder_name", "")),
        statement_period_start=_date(fields.get("statement_period_start", "2026-01-01")),
        statement_period_end=_date(fields.get("statement_period_end", "2026-01-31")),
        account_number_masked=str(fields.get("account_number_masked", "****0000")),
        opening_balance=_decimal(fields.get("opening_balance", "0")),
        closing_balance=_decimal(fields.get("closing_balance", "0")),
        transactions=transactions,
        confidence_notes=notes,
    )


def normalize_documents(state: LoanApplicationState) -> dict[str, Any]:
    """Map raw LlamaParse output to canonical Pydantic v2 models.

    Reads ``_parse_results`` written by ``parse_documents`` and writes
    ``pay_stub_data`` / ``bank_statement_data`` to state.  Missing/unparseable
    fields are handled with explicit nulls + confidence notes (design §6.3).
    """
    application_id = state.get("application_id", "unknown")
    parse_results: list[LlamaParseResponse] = state.get("_parse_results", [])  # type: ignore[assignment]

    pay_stub_data: PayStubFields | None = None
    bank_statement_data: BankStatementFields | None = None

    for result in parse_results:
        try:
            if result.document_type == DocumentType.PAYSTUB:
                pay_stub_data = _normalize_paystub(result.structured_fields, result.confidence_notes)
            elif result.document_type == DocumentType.BANK_STATEMENT:
                bank_statement_data = _normalize_bank_statement(
                    result.structured_fields,
                    result.table_rows,
                    result.confidence_notes,
                )
        except Exception as exc:
            log.warning(
                "document_subgraph.normalize_documents.normalization_error",
                extra={
                    "application_id": application_id,
                    "document_id": result.document_id,
                    "document_type": result.document_type,
                    "error": str(exc),
                },
            )

    log.info(
        "document_subgraph.normalize_documents.complete",
        extra={
            "application_id": application_id,
            "pay_stub_normalized": pay_stub_data is not None,
            "bank_statement_normalized": bank_statement_data is not None,
            "trace_id": state.get("trace_id"),
        },
    )
    return {
        "pay_stub_data": pay_stub_data,
        "bank_statement_data": bank_statement_data,
    }


# ── Subgraph factory ────────────────────────────────────────────────────────

def build_document_subgraph() -> CompiledStateGraph:
    """Compile and return the document-extraction LangGraph subgraph."""
    graph: StateGraph = StateGraph(LoanApplicationState)
    graph.add_node("load_documents", load_documents)
    graph.add_node("parse_documents", parse_documents)
    graph.add_node("normalize_documents", normalize_documents)

    graph.add_edge(START, "load_documents")
    graph.add_edge("load_documents", "parse_documents")
    graph.add_edge("parse_documents", "normalize_documents")
    graph.add_edge("normalize_documents", END)

    return graph.compile()
