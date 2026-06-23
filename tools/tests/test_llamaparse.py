"""Tests for the LlamaParse tool entry point (offline stub path) — P4-T1/T9.

These tests cover the fixture-stub path only (no API key required).
Live API tests would require LLAMA_CLOUD_API_KEY and are integration-level.
"""

import pytest

from shared.schemas import DocumentType
from tools.llamaparse import LlamaParseRequest, LlamaParseResponse, parse_financial_pdf
from tools.llamaparse.client import LlamaParseClient


# ── Client configuration check ───────────────────────────────────────────────

class TestClientConfiguration:
    def test_no_api_key_returns_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        client = LlamaParseClient()
        assert client.is_configured() is False

    def test_with_api_key_returns_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "test-key-123")
        client = LlamaParseClient()
        assert client.is_configured() is True


# ── parse_financial_pdf uses stub when no API key ────────────────────────────

class TestParseFinancialPdfStubPath:
    def test_paystub_stub_returns_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        req = LlamaParseRequest(
            application_id="app-lp-001",
            document_id="doc-001",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app-lp-001/paystub.pdf",
        )
        resp = parse_financial_pdf(req)
        assert isinstance(resp, LlamaParseResponse)

    def test_bank_statement_stub_returns_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        req = LlamaParseRequest(
            application_id="app-lp-002",
            document_id="doc-002",
            document_type=DocumentType.BANK_STATEMENT,
            s3_key="incoming/app-lp-002/statement.pdf",
        )
        resp = parse_financial_pdf(req)
        assert isinstance(resp, LlamaParseResponse)

    def test_stub_response_has_required_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        req = LlamaParseRequest(
            application_id="app-lp-003",
            document_id="doc-003",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app-lp-003/paystub.pdf",
        )
        resp = parse_financial_pdf(req)
        assert resp.application_id == req.application_id
        assert resp.document_id == req.document_id
        assert resp.document_type == DocumentType.PAYSTUB
        assert resp.raw_markdown
        assert isinstance(resp.structured_fields, dict)
        assert isinstance(resp.confidence_notes, list)

    def test_stub_is_deterministic_across_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        req = LlamaParseRequest(
            application_id="app-determinism",
            document_id="doc-determinism",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app-determinism/paystub.pdf",
        )
        r1 = parse_financial_pdf(req)
        r2 = parse_financial_pdf(req)
        assert r1.structured_fields == r2.structured_fields
        assert r1.raw_markdown == r2.raw_markdown

    def test_stub_includes_stub_confidence_note(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        req = LlamaParseRequest(
            application_id="app-note-check",
            document_id="doc-note",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app-note-check/paystub.pdf",
        )
        resp = parse_financial_pdf(req)
        assert any("stub_mode" in n for n in resp.confidence_notes)

    def test_bank_statement_stub_has_transaction_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
        req = LlamaParseRequest(
            application_id="app-rows",
            document_id="doc-rows",
            document_type=DocumentType.BANK_STATEMENT,
            s3_key="incoming/app-rows/statement.pdf",
        )
        resp = parse_financial_pdf(req)
        assert len(resp.table_rows) >= 1


# ── Request model validation ──────────────────────────────────────────────────

class TestRequestModel:
    def test_default_parse_profile_is_auto(self) -> None:
        req = LlamaParseRequest(
            application_id="app-profile",
            document_id="doc-profile",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app-profile/doc.pdf",
        )
        assert req.parse_profile == "auto"

    def test_custom_parse_profile(self) -> None:
        req = LlamaParseRequest(
            application_id="app-custom",
            document_id="doc-custom",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app-custom/doc.pdf",
            parse_profile="paystub_v1",
        )
        assert req.parse_profile == "paystub_v1"
