"""Canonical normalization layer — maps LlamaParse output → canonical schemas (P4-T2).

Design §6.3: A normalization step maps parser outputs to the system's canonical
schema, isolating the rest of the system from parser-specific output differences.

Supported document types:
  - ``PAYSTUB``         → :class:`shared.schemas.PayStubFields`
  - ``BANK_STATEMENT``  → :class:`shared.schemas.BankStatementFields`

All missing fields are handled with explicit ``None`` values and surfaced through
``confidence_notes`` rather than silently ignored or defaulted with incorrect data.

The normalization functions operate on the raw markdown extracted by LlamaParse
and attempt to parse it into structured fields using a two-pass strategy:
  1. Look for fields in the LlamaParse structured output (key-value pairs).
  2. Fall back to simple regex extraction from the raw markdown.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from tools.llamaparse.models import LlamaParseRawOutput, LlamaParseRequest, LlamaParseResponse
from tools.log import get_logger
from shared.schemas import DocumentType

log = get_logger("llamaparse.normalize")


def _parse_decimal(value: Any, field_name: str, notes: list[str]) -> Decimal | None:
    """Parse a value as Decimal; append a confidence note on failure."""
    if value is None:
        notes.append(f"missing_field:{field_name}")
        return None
    cleaned = str(value).replace(",", "").replace("$", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        notes.append(f"parse_error:{field_name}:could_not_parse_decimal:{value!r}")
        return None


def _parse_date(value: Any, field_name: str, notes: list[str]) -> date | None:
    """Parse a value as date; append a confidence note on failure."""
    if value is None:
        notes.append(f"missing_field:{field_name}")
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    notes.append(f"parse_error:{field_name}:unknown_date_format:{value!r}")
    return None


def _extract_markdown_field(markdown: str, *patterns: str) -> str | None:
    """Extract the first regex group match from raw markdown.

    Args:
        markdown: Raw markdown text from LlamaParse.
        patterns: Regex patterns to try in order; first match wins.

    Returns:
        Stripped match group 1, or None if no pattern matches.
    """
    for pattern in patterns:
        match = re.search(pattern, markdown, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _normalize_paystub(
    raw: LlamaParseRawOutput,
    request: LlamaParseRequest,
) -> LlamaParseResponse:
    """Normalize LlamaParse raw output for a PAYSTUB document.

    Args:
        raw: Raw output from the LlamaParse client.
        request: Original parse request (for IDs and document metadata).

    Returns:
        :class:`LlamaParseResponse` with structured paystub fields.
    """
    notes: list[str] = []
    ctx = {"application_id": request.application_id, "document_id": request.document_id}
    md = raw.raw_markdown

    employee_name = _extract_markdown_field(
        md,
        r"(?:employee[:\s]+name|employee name)[:\s]+([^\n]+)",
        r"(?:name|employee)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
    )
    if not employee_name:
        notes.append("missing_field:employee_name")

    employer_name = _extract_markdown_field(
        md,
        r"(?:employer name|company name|employer)[:\s]+([^\n]+)",
        r"(?:pay stub for|issued by)[:\s]+([^\n]+)",
    )
    if not employer_name:
        notes.append("missing_field:employer_name")

    pay_period_start_raw = _extract_markdown_field(
        md,
        r"(?:pay period start|period start|from)[:\s]+([\d/\-A-Za-z, ]+)",
    )
    pay_period_end_raw = _extract_markdown_field(
        md,
        r"(?:pay period end|period end|to)[:\s]+([\d/\-A-Za-z, ]+)",
    )
    pay_date_raw = _extract_markdown_field(
        md,
        r"(?:pay date|payment date|date paid)[:\s]+([\d/\-A-Za-z, ]+)",
    )
    gross_pay_raw = _extract_markdown_field(
        md,
        r"(?:gross pay|gross earnings|total gross)[:\s]+\$?([\d,]+\.?\d*)",
    )
    deductions_raw = _extract_markdown_field(
        md,
        r"(?:total deductions?|deductions)[:\s]+\$?([\d,]+\.?\d*)",
    )
    net_pay_raw = _extract_markdown_field(
        md,
        r"(?:net pay|take.home|net earnings)[:\s]+\$?([\d,]+\.?\d*)",
    )
    ytd_gross_raw = _extract_markdown_field(
        md,
        r"(?:ytd gross|year.to.date gross|ytd earnings)[:\s]+\$?([\d,]+\.?\d*)",
    )
    ytd_net_raw = _extract_markdown_field(
        md,
        r"(?:ytd net|year.to.date net)[:\s]+\$?([\d,]+\.?\d*)",
    )

    gross_pay = _parse_decimal(gross_pay_raw, "gross_pay", notes)
    deductions = _parse_decimal(deductions_raw, "deductions", notes)
    net_pay = _parse_decimal(net_pay_raw, "net_pay", notes)
    pay_period_start = _parse_date(pay_period_start_raw, "pay_period_start", notes)
    pay_period_end = _parse_date(pay_period_end_raw, "pay_period_end", notes)
    pay_date = _parse_date(pay_date_raw, "pay_date", notes)
    ytd_gross = _parse_decimal(ytd_gross_raw, "ytd_gross_pay", []) if ytd_gross_raw else None
    ytd_net = _parse_decimal(ytd_net_raw, "ytd_net_pay", []) if ytd_net_raw else None

    structured: dict[str, Any] = {
        "employee_name": employee_name,
        "employer_name": employer_name,
        "pay_period_start": str(pay_period_start) if pay_period_start else None,
        "pay_period_end": str(pay_period_end) if pay_period_end else None,
        "pay_date": str(pay_date) if pay_date else None,
        "gross_pay": str(gross_pay) if gross_pay is not None else None,
        "deductions": str(deductions) if deductions is not None else None,
        "net_pay": str(net_pay) if net_pay is not None else None,
        "ytd_gross_pay": str(ytd_gross) if ytd_gross is not None else None,
        "ytd_net_pay": str(ytd_net) if ytd_net is not None else None,
    }

    if notes:
        log.warning("paystub normalization confidence issues", correlation=ctx, notes=notes)

    return LlamaParseResponse(
        application_id=request.application_id,
        document_id=request.document_id,
        document_type=request.document_type,
        raw_markdown=raw.raw_markdown,
        structured_fields=structured,
        table_rows=[],
        confidence_notes=notes,
        document_metadata={
            "source": "llamaparse_api",
            "job_id": raw.job_id,
            "page_count": len(raw.pages),
            **raw.metadata,
        },
    )


def _normalize_bank_statement(
    raw: LlamaParseRawOutput,
    request: LlamaParseRequest,
) -> LlamaParseResponse:
    """Normalize LlamaParse raw output for a BANK_STATEMENT document.

    Args:
        raw: Raw output from the LlamaParse client.
        request: Original parse request.

    Returns:
        :class:`LlamaParseResponse` with structured bank statement fields.
    """
    notes: list[str] = []
    ctx = {"application_id": request.application_id, "document_id": request.document_id}
    md = raw.raw_markdown

    account_holder = _extract_markdown_field(
        md,
        r"(?:account holder|account name|customer name)[:\s]+([^\n]+)",
        r"(?:name)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
    )
    if not account_holder:
        notes.append("missing_field:account_holder_name")

    period_start_raw = _extract_markdown_field(
        md,
        r"(?:statement period|period)[:\s]+from\s+([\d/\-A-Za-z, ]+)",
        r"(?:from|start date)[:\s]+([\d/\-A-Za-z, ]+)",
    )
    period_end_raw = _extract_markdown_field(
        md,
        r"(?:statement period|period)[:\s]+.*?to\s+([\d/\-A-Za-z, ]+)",
        r"(?:to|end date)[:\s]+([\d/\-A-Za-z, ]+)",
    )
    account_masked = _extract_markdown_field(
        md,
        r"(?:account number?|acct\.?)[:\s]+(\*+\d{4}|\d{4})",
        r"(\*{3,}\d{4})",
    )
    if not account_masked:
        notes.append("missing_field:account_number_masked")
    opening_raw = _extract_markdown_field(
        md,
        r"(?:opening balance|beginning balance|balance forward)[:\s]+\$?([\d,]+\.?\d*)",
    )
    closing_raw = _extract_markdown_field(
        md,
        r"(?:closing balance|ending balance|balance as of)[:\s]+\$?([\d,]+\.?\d*)",
    )

    period_start = _parse_date(period_start_raw, "statement_period_start", notes)
    period_end = _parse_date(period_end_raw, "statement_period_end", notes)
    opening = _parse_decimal(opening_raw, "opening_balance", notes)
    closing = _parse_decimal(closing_raw, "closing_balance", notes)

    # Extract transaction rows from markdown tables
    table_rows = _extract_transaction_rows(md, notes)

    structured: dict[str, Any] = {
        "account_holder_name": account_holder,
        "statement_period_start": str(period_start) if period_start else None,
        "statement_period_end": str(period_end) if period_end else None,
        "account_number_masked": account_masked,
        "opening_balance": str(opening) if opening is not None else None,
        "closing_balance": str(closing) if closing is not None else None,
    }

    if notes:
        log.warning("bank statement normalization confidence issues", correlation=ctx, notes=notes)

    return LlamaParseResponse(
        application_id=request.application_id,
        document_id=request.document_id,
        document_type=request.document_type,
        raw_markdown=raw.raw_markdown,
        structured_fields=structured,
        table_rows=table_rows,
        confidence_notes=notes,
        document_metadata={
            "source": "llamaparse_api",
            "job_id": raw.job_id,
            "page_count": len(raw.pages),
            **raw.metadata,
        },
    )


def _extract_transaction_rows(markdown: str, notes: list[str]) -> list[dict[str, Any]]:
    """Extract transaction rows from a markdown table in the bank statement.

    Looks for a pipe-delimited markdown table with date/description/amount/balance.
    Returns a list of row dicts; appends a confidence note if extraction fails.

    Args:
        markdown: Raw markdown text from LlamaParse.
        notes: Mutable list to append confidence notes.

    Returns:
        List of row dicts with keys: date, description, amount, balance.
    """
    # Match markdown table rows: | date | desc | amount | balance |
    row_pattern = re.compile(
        r"\|\s*([\d/\-]+)\s*\|\s*([^|]+)\s*\|\s*([-$\d,.]+)\s*\|\s*([-$\d,.]*)\s*\|",
        re.MULTILINE,
    )
    rows: list[dict[str, Any]] = []
    for match in row_pattern.finditer(markdown):
        date_str = match.group(1).strip()
        description = match.group(2).strip()
        amount_str = match.group(3).strip().replace("$", "").replace(",", "")
        balance_str = match.group(4).strip().replace("$", "").replace(",", "")

        # Skip header separator rows
        if re.match(r"[-:]+", date_str):
            continue

        row: dict[str, Any] = {"date": date_str, "description": description, "amount": amount_str}
        if balance_str:
            row["balance"] = balance_str
        rows.append(row)

    if not rows:
        notes.append("confidence:no_transaction_rows_extracted_from_markdown")
    return rows


def normalize_response(raw: LlamaParseRawOutput, request: LlamaParseRequest) -> LlamaParseResponse:
    """Dispatch normalization by document type.

    Args:
        raw: Raw output from the LlamaParse API client.
        request: Original parse request.

    Returns:
        Normalized :class:`LlamaParseResponse` matching the Gateway contract.
    """
    if request.document_type == DocumentType.PAYSTUB:
        return _normalize_paystub(raw, request)
    if request.document_type == DocumentType.BANK_STATEMENT:
        return _normalize_bank_statement(raw, request)

    # OTHER / ID — return raw markdown with no structured normalization
    return LlamaParseResponse(
        application_id=request.application_id,
        document_id=request.document_id,
        document_type=request.document_type,
        raw_markdown=raw.raw_markdown,
        structured_fields={},
        table_rows=[],
        confidence_notes=["normalization:unsupported_document_type"],
        document_metadata={
            "source": "llamaparse_api",
            "job_id": raw.job_id,
            **raw.metadata,
        },
    )
