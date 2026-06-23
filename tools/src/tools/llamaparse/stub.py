"""Deterministic fixture stub for offline / CI use — no LlamaParse API required.

Returns the same fixture fields for a given (application_id, document_id, document_type)
tuple so graph tests remain reproducible without network access.
"""

import hashlib
from decimal import Decimal
from typing import Any

from tools.llamaparse.models import LlamaParseRequest, LlamaParseResponse
from shared.schemas import DocumentType


def _paystub_fields(seed: str) -> dict[str, Any]:
    """Return deterministic synthetic pay-stub structured fields."""
    gross = Decimal("5500.00") + Decimal(int(hashlib.md5(seed.encode()).hexdigest()[:4], 16) % 4000)
    net = (gross * Decimal("0.72")).quantize(Decimal("0.01"))
    deductions = (gross - net).quantize(Decimal("0.01"))
    return {
        "employee_name": "Jane Doe",
        "employer_name": "Acme Corp",
        "pay_period_start": "2026-05-01",
        "pay_period_end": "2026-05-31",
        "pay_date": "2026-06-01",
        "gross_pay": str(gross),
        "deductions": str(deductions),
        "net_pay": str(net),
        "ytd_gross_pay": str((gross * 5).quantize(Decimal("0.01"))),
        "ytd_net_pay": str((net * 5).quantize(Decimal("0.01"))),
    }


def _bank_statement_fields(seed: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return deterministic synthetic bank-statement fields + transaction rows."""
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
    rows: list[dict[str, Any]] = [
        {"date": "2026-05-03", "description": "Direct Deposit", "amount": "3000.00",
         "balance": str(opening + Decimal("3000.00"))},
        {"date": "2026-05-10", "description": "Rent Payment", "amount": "-1500.00",
         "balance": str(opening + Decimal("1500.00"))},
        {"date": "2026-05-15", "description": "Grocery Store", "amount": "-150.00",
         "balance": str(opening + Decimal("1350.00"))},
    ]
    return fields, rows


def use_fixture_stub(request: LlamaParseRequest) -> LlamaParseResponse:
    """Return a deterministic fixture response for offline/CI use.

    Args:
        request: :class:`LlamaParseRequest` from the caller.

    Returns:
        :class:`LlamaParseResponse` populated with stable synthetic values.
    """
    seed = f"{request.application_id}:{request.document_id}"
    stub_note = "stub_mode:deterministic_fixture_no_api_key"

    if request.document_type == DocumentType.PAYSTUB:
        structured = _paystub_fields(seed)
        raw_markdown = (
            f"# Pay Stub\n\n"
            f"Employee Name: {structured['employee_name']}\n"
            f"Employer Name: {structured['employer_name']}\n"
            f"Pay Period: {structured['pay_period_start']} to {structured['pay_period_end']}\n"
            f"Pay Date: {structured['pay_date']}\n"
            f"Gross Pay: {structured['gross_pay']}\n"
            f"Deductions: {structured['deductions']}\n"
            f"Net Pay: {structured['net_pay']}\n"
        )
        return LlamaParseResponse(
            application_id=request.application_id,
            document_id=request.document_id,
            document_type=request.document_type,
            raw_markdown=raw_markdown,
            structured_fields=structured,
            table_rows=[],
            confidence_notes=[stub_note],
            document_metadata={"source": "stub", "page_count": 1},
        )

    # BANK_STATEMENT
    structured_stmt, rows = _bank_statement_fields(seed)
    raw_markdown = (
        f"# Bank Statement\n\n"
        f"Account Holder: {structured_stmt['account_holder_name']}\n"
        f"Statement Period: {structured_stmt['statement_period_start']} "
        f"to {structured_stmt['statement_period_end']}\n"
        f"Account Number: {structured_stmt['account_number_masked']}\n"
        f"Opening Balance: {structured_stmt['opening_balance']}\n"
        f"Closing Balance: {structured_stmt['closing_balance']}\n"
    )
    return LlamaParseResponse(
        application_id=request.application_id,
        document_id=request.document_id,
        document_type=request.document_type,
        raw_markdown=raw_markdown,
        structured_fields=structured_stmt,
        table_rows=rows,
        confidence_notes=[stub_note],
        document_metadata={"source": "stub", "page_count": 1},
    )
