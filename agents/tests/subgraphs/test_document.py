"""Unit tests for the document-extraction subgraph (P3-T4, P3-T12).

Tests cover:
* Happy-path: both docs present → pay_stub_data + bank_statement_data set
* Empty inventory → parse_failure_count incremented
* Normalization edge cases (missing optional fields default gracefully)
* Subgraph compilation and invocability
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from agents.subgraphs.document import (
    build_document_subgraph,
    load_documents,
    normalize_documents,
    parse_documents,
)
from shared.schemas import Document, DocumentType


def _make_document(doc_type: DocumentType, application_id: str = "app_001") -> Document:

    return Document(
        document_id=f"doc_{doc_type.lower()}",
        application_id=application_id,
        document_type=doc_type,
        s3_key=f"incoming/{application_id}/{doc_type.lower()}.pdf",
        uploaded_at=datetime.now(UTC),
        parse_status="PENDING",
    )


def _base_state(application_id: str = "app_001") -> dict:
    return {
        "application_id": application_id,
        "user_id": "user_123",
        "trace_id": "trace_abc",
        "document_inventory": [
            _make_document(DocumentType.PAYSTUB, application_id),
            _make_document(DocumentType.BANK_STATEMENT, application_id),
        ],
        "parse_failure_count": 0,
    }


class TestLoadDocumentsNode:
    def test_marks_documents_processing(self) -> None:
        state = _base_state()
        result = load_documents(state)
        updated = result["document_inventory"]
        assert all(doc.parse_status == "PROCESSING" for doc in updated)

    def test_empty_inventory_increments_failure(self) -> None:
        state = _base_state()
        state["document_inventory"] = []
        result = load_documents(state)
        assert result["parse_failure_count"] == 1


class TestParseDocumentsNode:
    def test_happy_path_produces_parse_results(self) -> None:
        state = _base_state()
        result = parse_documents(state)
        assert result["parse_failure_count"] == 0
        parse_results = result.get("_parse_results", [])
        assert len(parse_results) == 2

    def test_parse_results_have_correct_types(self) -> None:
        state = _base_state()
        result = parse_documents(state)
        parse_results = result["_parse_results"]
        types = {r.document_type for r in parse_results}
        assert DocumentType.PAYSTUB in types
        assert DocumentType.BANK_STATEMENT in types


class TestNormalizeDocumentsNode:
    def _build_state_with_parse_results(self, application_id: str = "app_001") -> dict:
        """Run parse_documents and load its results into state for normalization."""
        state = _base_state(application_id)
        parse_state = {**state, **parse_documents(state)}
        return parse_state

    def test_pay_stub_normalized(self) -> None:
        state = self._build_state_with_parse_results()
        result = normalize_documents(state)
        assert result["pay_stub_data"] is not None
        ps = result["pay_stub_data"]
        assert ps.gross_pay > Decimal("0")
        assert ps.employee_name != ""

    def test_bank_statement_normalized(self) -> None:
        state = self._build_state_with_parse_results()
        result = normalize_documents(state)
        assert result["bank_statement_data"] is not None
        bs = result["bank_statement_data"]
        assert bs.closing_balance >= Decimal("0")
        assert bs.account_holder_name != ""

    def test_no_parse_results_returns_none(self) -> None:
        state = _base_state()
        state["_parse_results"] = []  # type: ignore[typeddict-unknown-key]
        result = normalize_documents(state)
        assert result.get("pay_stub_data") is None
        assert result.get("bank_statement_data") is None


class TestDocumentSubgraphEndToEnd:
    def test_subgraph_compiles(self) -> None:
        subgraph = build_document_subgraph()
        assert subgraph is not None

    def test_subgraph_happy_path(self) -> None:
        subgraph = build_document_subgraph()
        state = _base_state()
        result = subgraph.invoke(state)
        assert result.get("pay_stub_data") is not None
        assert result.get("bank_statement_data") is not None
        assert result.get("parse_failure_count", 0) == 0

    def test_subgraph_empty_inventory(self) -> None:
        subgraph = build_document_subgraph()
        state = _base_state()
        state["document_inventory"] = []
        result = subgraph.invoke(state)
        assert result.get("parse_failure_count", 0) >= 1
