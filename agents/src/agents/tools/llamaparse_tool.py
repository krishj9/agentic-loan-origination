"""LlamaParse tool interface — ``llamaparse.parse_financial_pdf`` (P3-T10).

This module defines:
* ``LlamaParseRequest`` / ``LlamaParseResponse`` — stable Pydantic v2 contracts
  matching the Gateway spec in ``agents.tools.schemas``.
* ``call_llamaparse(request)`` — callable invoked by the document-extraction
  subgraph.  It delegates to ``agents.tools.llamaparse`` (Phase 4) when
  available, and falls back to a deterministic stub for offline tests.

The stub is *not* random — for a given (document_type, application_id) pair it
always returns the same fixture fields so graph tests remain reproducible.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas import DocumentType

# ── Request / Response models ───────────────────────────────────────────────

class LlamaParseRequest(BaseModel):
    """Input contract for ``llamaparse.parse_financial_pdf``."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Application identifier for correlation.")
    document_id: str = Field(description="Document identifier within the application.")
    document_type: DocumentType = Field(description="Document class driving the parse profile.")
    s3_key: str = Field(description="Full S3 key under incoming/{application_id}/.")
    parse_profile: str = Field(
        default="auto",
        description="Named parse profile (e.g. 'paystub_v1', 'bank_statement_v1').",
    )


class LlamaParseResponse(BaseModel):
    """Output contract for ``llamaparse.parse_financial_pdf`` (design §6.2)."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Mirrors the request application_id.")
    document_id: str = Field(description="Mirrors the request document_id.")
    document_type: DocumentType = Field(description="Mirrors the request document_type.")
    raw_markdown: str = Field(description="Full document text rendered as Markdown by LlamaParse.")
    structured_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value extraction produced by LlamaParse structured output mode.",
    )
    table_rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tabular rows extracted from the document (e.g. transaction table).",
    )
    confidence_notes: list[str] = Field(
        default_factory=list,
        description="Parser confidence notes or extraction warnings.",
    )
    document_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level metadata (page count, format, extraction timestamp).",
    )


# ── Stub implementation ─────────────────────────────────────────────────────

def _stub_paystub_fields(seed: str) -> dict[str, Any]:
    """Return deterministic synthetic pay-stub structured fields."""
    gross = Decimal("5500.00") + Decimal(int(hashlib.md5(seed.encode()).hexdigest()[:4], 16) % 4000)
    net = (gross * Decimal("0.72")).quantize(Decimal("0.01"))
    return {
        "employee_name": "Jane Doe",
        "employer_name": "Acme Corp",
        "pay_period_start": "2026-05-01",
        "pay_period_end": "2026-05-31",
        "pay_date": "2026-06-01",
        "gross_pay": str(gross),
        "deductions": str((gross - net).quantize(Decimal("0.01"))),
        "net_pay": str(net),
        "ytd_gross_pay": str((gross * 5).quantize(Decimal("0.01"))),
        "ytd_net_pay": str((net * 5).quantize(Decimal("0.01"))),
    }


def _stub_bank_statement_fields(seed: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return deterministic synthetic bank-statement structured fields + rows."""
    opening = Decimal("4200.00") + Decimal(int(hashlib.md5(seed.encode()).hexdigest()[4:8], 16) % 2000)
    closing = (opening + Decimal("350.00")).quantize(Decimal("0.01"))
    fields = {
        "account_holder_name": "Jane Doe",
        "statement_period_start": "2026-05-01",
        "statement_period_end": "2026-05-31",
        "account_number_masked": "****1234",
        "opening_balance": str(opening),
        "closing_balance": str(closing),
    }
    rows = [
        {"date": "2026-05-03", "description": "Direct Deposit", "amount": "3000.00",
         "balance": str(opening + Decimal("3000"))},
        {"date": "2026-05-10", "description": "Rent Payment", "amount": "-1500.00",
         "balance": str(opening + Decimal("1500"))},
        {"date": "2026-05-15", "description": "Grocery Store", "amount": "-150.00",
         "balance": str(opening + Decimal("1350"))},
    ]
    return fields, rows


def _call_stub(request: LlamaParseRequest) -> LlamaParseResponse:
    """Return deterministic fixture data for offline / CI use."""
    seed = f"{request.application_id}:{request.document_id}"
    _stub_note = "stub_mode: deterministic fixture — replace with Phase 4 LlamaParse implementation"
    if request.document_type == DocumentType.PAYSTUB:
        structured = _stub_paystub_fields(seed)
        raw = f"# Pay Stub\n\nEmployee: {structured['employee_name']}\nGross Pay: {structured['gross_pay']}"
        rows: list[dict[str, Any]] = []
        notes = [_stub_note]
    else:
        structured, rows = _stub_bank_statement_fields(seed)
        holder = structured["account_holder_name"]
        balance = structured["closing_balance"]
        raw = f"# Bank Statement\n\nAccount Holder: {holder}\nClosing Balance: {balance}"
        notes = [_stub_note]
    return LlamaParseResponse(
        application_id=request.application_id,
        document_id=request.document_id,
        document_type=request.document_type,
        raw_markdown=raw,
        structured_fields=structured,
        table_rows=rows,
        confidence_notes=notes,
        document_metadata={"source": "stub", "page_count": 1},
    )


def call_llamaparse(request: LlamaParseRequest) -> LlamaParseResponse:
    """Invoke the LlamaParse financial-PDF parser.

    Delegates to the Phase 4 implementation (``tools.llamaparse.parse_financial_pdf``) when
    available; falls back to the deterministic stub otherwise.

    Args:
        request: Validated ``LlamaParseRequest`` with all required fields.

    Returns:
        ``LlamaParseResponse`` with extracted fields, raw markdown, and notes.
    """
    try:
        from tools.llamaparse import parse_financial_pdf  # Phase 4

        return parse_financial_pdf(request)
    except ImportError:
        return _call_stub(request)


# ── Gateway-compatible tool definition ─────────────────────────────────────
#   Returned by the tool function for AgentCore Gateway schema introspection.

def get_tool_spec() -> dict[str, Any] | None:
    """Return the Gateway tool specification for this tool."""
    from agents.tools.schemas import LLAMAPARSE_TOOL_SPEC

    return LLAMAPARSE_TOOL_SPEC
