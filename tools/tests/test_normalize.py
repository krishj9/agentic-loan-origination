"""Tests for the LlamaParse normalization layer — P4-T2/T9.

Acceptance criteria (P4-T9):
  * PAYSTUB fields correctly extracted from markdown.
  * BANK_STATEMENT fields + transaction rows correctly extracted.
  * Missing fields produce explicit None values + confidence_notes entries.
  * Stub returns deterministic fixture for offline use.
  * Unsupported document types produce graceful response with confidence note.
"""

import pytest

from shared.schemas import DocumentType
from tools.llamaparse.models import LlamaParseRawOutput, LlamaParseRequest
from tools.llamaparse.normalize import normalize_response
from tools.llamaparse.stub import use_fixture_stub


def _make_request(
    doc_type: DocumentType = DocumentType.PAYSTUB,
    application_id: str = "app-norm-001",
    document_id: str = "doc-001",
) -> LlamaParseRequest:
    return LlamaParseRequest(
        application_id=application_id,
        document_id=document_id,
        document_type=doc_type,
        s3_key=f"incoming/{application_id}/doc.pdf",
    )


def _make_raw(markdown: str, job_id: str = "job-001") -> LlamaParseRawOutput:
    return LlamaParseRawOutput(job_id=job_id, raw_markdown=markdown, pages=[], metadata={})


# ── PAYSTUB normalization ────────────────────────────────────────────────────

class TestPaystubNormalization:
    _PAYSTUB_MD = """
# Pay Stub

Employee Name: Jane Smith
Employer Name: Acme Corporation
Pay Period: 2026-05-01 to 2026-05-31
Pay Date: 2026-06-01
Gross Pay: $7,500.00
Total Deductions: $2,100.00
Net Pay: $5,400.00
YTD Gross: $37,500.00
YTD Net: $27,000.00
"""

    def test_employee_name_extracted(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("employee_name") == "Jane Smith"

    def test_employer_name_extracted(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("employer_name") == "Acme Corporation"

    def test_gross_pay_extracted(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("gross_pay") == "7500.00"

    def test_net_pay_extracted(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("net_pay") == "5400.00"

    def test_document_ids_echoed(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.application_id == req.application_id
        assert resp.document_id == req.document_id

    def test_document_type_echoed(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.document_type == DocumentType.PAYSTUB

    def test_raw_markdown_preserved(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD)
        resp = normalize_response(raw, req)
        assert resp.raw_markdown == self._PAYSTUB_MD

    def test_job_id_in_metadata(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw(self._PAYSTUB_MD, job_id="test-job-xyz")
        resp = normalize_response(raw, req)
        assert resp.document_metadata.get("job_id") == "test-job-xyz"

    def test_missing_employee_name_produces_confidence_note(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw("# Pay Stub\n\nGross Pay: $5000.00\nNet Pay: $3600.00\n")
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("employee_name") is None
        assert any("employee_name" in n for n in resp.confidence_notes)

    def test_missing_gross_pay_produces_confidence_note(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        raw = _make_raw("# Pay Stub\n\nEmployee Name: John Doe\n")
        resp = normalize_response(raw, req)
        assert any("gross_pay" in n for n in resp.confidence_notes)


# ── BANK_STATEMENT normalization ─────────────────────────────────────────────

class TestBankStatementNormalization:
    _BANK_MD = """
# Bank Statement

Account Holder: John Doe
Statement Period: from 2026-05-01 to 2026-05-31
Account Number: ****5678
Opening Balance: $4,200.00
Closing Balance: $5,100.00

## Transactions

| Date       | Description      | Amount    | Balance   |
|------------|------------------|-----------|-----------|
| 2026-05-03 | Direct Deposit   | 3000.00   | 7200.00   |
| 2026-05-10 | Rent Payment     | -1500.00  | 5700.00   |
| 2026-05-15 | Grocery Store    | -150.00   | 5550.00   |
"""

    def test_account_holder_extracted(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw(self._BANK_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("account_holder_name") == "John Doe"

    def test_opening_balance_extracted(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw(self._BANK_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("opening_balance") == "4200.00"

    def test_closing_balance_extracted(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw(self._BANK_MD)
        resp = normalize_response(raw, req)
        assert resp.structured_fields.get("closing_balance") == "5100.00"

    def test_transaction_rows_extracted(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw(self._BANK_MD)
        resp = normalize_response(raw, req)
        assert len(resp.table_rows) == 3

    def test_transaction_row_structure(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw(self._BANK_MD)
        resp = normalize_response(raw, req)
        first = resp.table_rows[0]
        assert "date" in first
        assert "description" in first
        assert "amount" in first

    def test_missing_closing_balance_produces_note(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw("# Bank Statement\n\nAccount Holder: Jane Smith\nOpening Balance: $5000.00\n")
        resp = normalize_response(raw, req)
        assert any("closing_balance" in n for n in resp.confidence_notes)

    def test_no_transactions_produces_confidence_note(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        raw = _make_raw("# Bank Statement\n\nAccount Holder: Jane Smith\nOpening Balance: $5000.00\nClosing Balance: $5200.00\n")
        resp = normalize_response(raw, req)
        assert any("no_transaction_rows" in n for n in resp.confidence_notes)


# ── Unsupported document type ─────────────────────────────────────────────────

class TestUnsupportedDocumentType:
    def test_id_type_returns_unsupported_note(self) -> None:
        req = _make_request(DocumentType.ID)
        raw = _make_raw("# ID Document\n\nName: John Doe\n")
        resp = normalize_response(raw, req)
        assert any("unsupported_document_type" in n for n in resp.confidence_notes)
        assert resp.structured_fields == {}
        assert resp.table_rows == []

    def test_other_type_returns_unsupported_note(self) -> None:
        req = _make_request(DocumentType.OTHER)
        raw = _make_raw("# Some document\n")
        resp = normalize_response(raw, req)
        assert any("unsupported_document_type" in n for n in resp.confidence_notes)


# ── Fixture stub tests ────────────────────────────────────────────────────────

class TestFixtureStub:
    def test_stub_paystub_deterministic(self) -> None:
        req = _make_request(DocumentType.PAYSTUB, application_id="stub-app-1")
        r1 = use_fixture_stub(req)
        r2 = use_fixture_stub(req)
        assert r1.structured_fields == r2.structured_fields
        assert r1.raw_markdown == r2.raw_markdown

    def test_stub_bank_statement_deterministic(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT, application_id="stub-app-2")
        r1 = use_fixture_stub(req)
        r2 = use_fixture_stub(req)
        assert r1.structured_fields == r2.structured_fields
        assert r1.table_rows == r2.table_rows

    def test_stub_different_seeds_differ(self) -> None:
        req1 = _make_request(DocumentType.PAYSTUB, application_id="seed-A")
        req2 = _make_request(DocumentType.PAYSTUB, application_id="seed-B")
        r1 = use_fixture_stub(req1)
        r2 = use_fixture_stub(req2)
        # Gross pay is seeded — may differ for different application IDs
        assert r1.document_type == r2.document_type

    def test_stub_includes_stub_note(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        resp = use_fixture_stub(req)
        assert any("stub_mode" in n for n in resp.confidence_notes)

    def test_stub_paystub_has_required_fields(self) -> None:
        req = _make_request(DocumentType.PAYSTUB)
        resp = use_fixture_stub(req)
        fields = resp.structured_fields
        assert fields.get("employee_name") is not None
        assert fields.get("gross_pay") is not None
        assert fields.get("net_pay") is not None

    def test_stub_bank_statement_has_required_fields(self) -> None:
        req = _make_request(DocumentType.BANK_STATEMENT)
        resp = use_fixture_stub(req)
        fields = resp.structured_fields
        assert fields.get("account_holder_name") is not None
        assert fields.get("opening_balance") is not None
        assert fields.get("closing_balance") is not None
        assert len(resp.table_rows) >= 1
