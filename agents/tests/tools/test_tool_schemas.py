"""Tests for tool interface schemas and stub callables (P3-T10, P3-T12).

Tests cover:
* Tool spec keys and required fields present
* LlamaParseRequest / Response round-trip
* RiskEngine stub is deterministic (same input → same output)
* ComplianceEngine stub applies rule thresholds correctly
* Packaging stub produces correct S3 key prefixes
* ALL_TOOL_SPECS has the four expected tool names
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from agents.tools.compliance_tool import ComplianceToolRequest, call_compliance_engine
from agents.tools.llamaparse_tool import LlamaParseRequest, call_llamaparse
from agents.tools.packaging_tool import PackagingToolRequest, call_packaging
from agents.tools.risk_engine_tool import RiskEngineRequest, call_risk_engine
from agents.tools.schemas import ALL_TOOL_SPECS
from shared.schemas import (
    AuditContext,
    ComplianceAction,
    Decision,
    DecisionOutcome,
    DocumentType,
    RiskProfile,
)


class TestAllToolSpecs:
    def test_four_tools_registered(self) -> None:
        assert len(ALL_TOOL_SPECS) == 4

    def test_expected_tool_names(self) -> None:
        names = {spec["name"] for spec in ALL_TOOL_SPECS}
        assert "llamaparse.parse_financial_pdf" in names
        assert "risk_engine.evaluate" in names
        assert "compliance_engine.evaluate" in names
        assert "packaging.generate_artifacts" in names

    def test_all_specs_have_input_schema(self) -> None:
        for spec in ALL_TOOL_SPECS:
            assert "inputSchema" in spec, f"Tool {spec['name']} missing inputSchema"
            assert "properties" in spec["inputSchema"]

    def test_all_specs_have_required_fields(self) -> None:
        for spec in ALL_TOOL_SPECS:
            assert "required" in spec["inputSchema"], f"Tool {spec['name']} missing required"


class TestLlamaParseToolInterface:
    def test_paystub_request_response(self) -> None:
        req = LlamaParseRequest(
            application_id="app_001",
            document_id="doc_ps",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app_001/paystub.pdf",
        )
        resp = call_llamaparse(req)
        assert resp.application_id == "app_001"
        assert resp.document_type == DocumentType.PAYSTUB
        assert "employee_name" in resp.structured_fields
        assert "gross_pay" in resp.structured_fields

    def test_bank_statement_request_response(self) -> None:
        req = LlamaParseRequest(
            application_id="app_001",
            document_id="doc_bs",
            document_type=DocumentType.BANK_STATEMENT,
            s3_key="incoming/app_001/bank_statement.pdf",
        )
        resp = call_llamaparse(req)
        assert resp.document_type == DocumentType.BANK_STATEMENT
        assert "account_holder_name" in resp.structured_fields
        assert "closing_balance" in resp.structured_fields

    def test_stub_confidence_notes_present(self) -> None:
        req = LlamaParseRequest(
            application_id="app_001",
            document_id="doc_ps",
            document_type=DocumentType.PAYSTUB,
            s3_key="incoming/app_001/paystub.pdf",
        )
        resp = call_llamaparse(req)
        assert len(resp.confidence_notes) > 0


class TestRiskEngineToolInterface:
    def _prime_request(self, app_id: str = "app_r_001") -> RiskEngineRequest:
        return RiskEngineRequest(
            applicant_id=app_id,
            annual_income=Decimal("90000"),
            debt_utilization=Decimal("0.20"),
        )

    def test_prime_profile_assigned(self) -> None:
        resp = call_risk_engine(self._prime_request())
        assert resp.risk_profile == RiskProfile.PRIME

    def test_near_prime_profile(self) -> None:
        req = RiskEngineRequest(
            applicant_id="app_np",
            annual_income=Decimal("60000"),
            debt_utilization=Decimal("0.40"),
        )
        resp = call_risk_engine(req)
        assert resp.risk_profile == RiskProfile.NEAR_PRIME

    def test_subprime_profile(self) -> None:
        req = RiskEngineRequest(
            applicant_id="app_sp",
            annual_income=Decimal("30000"),
            debt_utilization=Decimal("0.70"),
        )
        resp = call_risk_engine(req)
        assert resp.risk_profile == RiskProfile.SUBPRIME

    def test_override_pins_profile(self) -> None:
        req = RiskEngineRequest(
            applicant_id="app_override",
            annual_income=Decimal("100000"),
            debt_utilization=Decimal("0.10"),
            risk_profile=RiskProfile.SUBPRIME,
        )
        resp = call_risk_engine(req)
        assert resp.risk_profile == RiskProfile.SUBPRIME

    def test_deterministic_output(self) -> None:
        req = self._prime_request("app_determinism")
        resp_a = call_risk_engine(req)
        resp_b = call_risk_engine(req)
        assert resp_a.credit_score == resp_b.credit_score
        assert resp_a.risk_flags == resp_b.risk_flags
        assert resp_a.tradelines == resp_b.tradelines

    def test_explainability_fields_present(self) -> None:
        resp = call_risk_engine(self._prime_request())
        assert resp.income_band in ("HIGH", "MID", "LOW")
        assert resp.utilization_band in ("LOW", "MODERATE", "HIGH")
        assert len(resp.score_range_rationale) > 0


class TestComplianceToolInterface:
    def _approve_request(self) -> ComplianceToolRequest:
        return ComplianceToolRequest(
            application_id="app_c_001",
            annual_income=Decimal("120000"),
            requested_loan_amount=Decimal("20000"),
            risk_profile=RiskProfile.PRIME,
            document_types_present=["PAYSTUB", "BANK_STATEMENT"],
        )

    def test_approve_path(self) -> None:
        result = call_compliance_engine(self._approve_request())
        assert result.recommended_action == ComplianceAction.APPROVE
        assert result.passed is True

    def test_decline_missing_docs(self) -> None:
        req = ComplianceToolRequest(
            application_id="app_c_002",
            annual_income=Decimal("80000"),
            requested_loan_amount=Decimal("15000"),
            risk_profile=RiskProfile.PRIME,
            document_types_present=[],
        )
        result = call_compliance_engine(req)
        assert result.recommended_action == ComplianceAction.DECLINE

    def test_flags_include_all_rules(self) -> None:
        result = call_compliance_engine(self._approve_request())
        rule_ids = {f.rule_id for f in result.flags}
        assert "LOAN_TO_INCOME_RATIO" in rule_ids
        assert "RISK_BAND_LOAN_CEILING" in rule_ids
        assert "REQUIRED_DOCUMENT_COMPLETENESS" in rule_ids


class TestPackagingToolInterface:
    def _make_request(self, application_id: str = "app_p_001") -> PackagingToolRequest:
        decision = Decision(
            applicationId=application_id,
            outcome=DecisionOutcome.APPROVE,
            riskProfile=RiskProfile.PRIME,
            creditScore=745,
            rationale="Test rationale.",
        )
        audit_context = AuditContext(
            application_id=application_id,
            user_id="user_1",
            submission_timestamp=datetime(2026, 6, 22, 18, 0, 0, tzinfo=UTC),
        )
        return PackagingToolRequest(
            application_id=application_id,
            decision=decision,
            audit_context=audit_context,
            s3_bucket="test-bucket",
        )

    def test_json_key_prefix(self) -> None:
        result = call_packaging(self._make_request("app_p_999"))
        assert result.artifact_json_s3_key == "archive/app_p_999/decision.json"

    def test_pdf_key_prefix(self) -> None:
        result = call_packaging(self._make_request("app_p_999"))
        assert result.artifact_pdf_s3_key == "archive/app_p_999/decision.pdf"
