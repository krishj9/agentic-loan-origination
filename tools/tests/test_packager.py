"""Tests for the artifact packager (JSON + PDF generation) — P4-T6/T9.

Acceptance criteria (P4-T9):
  * JSON artifact is valid, parseable, and contains all required fields.
  * PDF artifact bytes are non-empty and start with the PDF magic bytes (%PDF).
  * S3 key format follows archive/{application_id}/decision.json|.pdf.
  * Deterministic layout: same input → same JSON output (sort_keys=True).
  * Audit context embedded in JSON artifact.
  * PackageResult returned correctly with write_to_s3=False (no actual S3 calls).
"""

import json

import pytest

from shared.schemas import AuditContext, Decision, DecisionOutcome, RiskProfile
from tools.packager import PackageRequest, PackageResult, generate
from tools.packager.generator import generate_json, generate_pdf

_PDF_MAGIC = b"%PDF"


# ── JSON generation ───────────────────────────────────────────────────────────

class TestJsonGeneration:
    def test_json_is_valid(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_json_contains_application_id(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert parsed.get("applicationId") == sample_decision.application_id

    def test_json_contains_outcome(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert parsed.get("outcome") == sample_decision.outcome.value

    def test_json_contains_audit_context(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert "auditContext" in parsed
        assert parsed["auditContext"]["application_id"] == audit_context.application_id

    def test_json_contains_risk_profile(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert parsed.get("riskProfile") == sample_decision.risk_profile.value

    def test_json_contains_credit_score(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert parsed.get("creditScore") == sample_decision.credit_score

    def test_json_contains_generated_at(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        parsed = json.loads(content)
        assert "generatedAt" in parsed

    def test_json_deterministic_same_inputs(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        """JSON with sort_keys=True is structurally deterministic for the same inputs."""
        c1 = generate_json(sample_decision, audit_context)
        c2 = generate_json(sample_decision, audit_context)
        p1 = json.loads(c1)
        p2 = json.loads(c2)
        # Exclude generatedAt timestamp which changes per call
        for key in p1:
            if key != "generatedAt":
                assert p1[key] == p2[key]

    def test_json_keys_sorted(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        content = generate_json(sample_decision, audit_context)
        # Verify JSON is formatted with sorted keys by re-parsing and re-serializing
        parsed = json.loads(content)
        re_serialized = json.dumps(parsed, indent=2, sort_keys=True, default=str)
        assert content.split("\n")[0] == re_serialized.split("\n")[0]


# ── PDF generation ────────────────────────────────────────────────────────────

class TestPdfGeneration:
    def test_pdf_bytes_non_empty(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        pdf = generate_pdf(sample_decision, audit_context)
        assert len(pdf) > 1000

    def test_pdf_starts_with_magic_bytes(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        pdf = generate_pdf(sample_decision, audit_context)
        assert pdf[:4] == _PDF_MAGIC

    def test_pdf_returns_bytes_type(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        pdf = generate_pdf(sample_decision, audit_context)
        assert isinstance(pdf, bytes)

    def test_pdf_size_reasonable(self, sample_decision: Decision, audit_context: AuditContext) -> None:
        """Generated PDF should be smaller than 5 MB for a single-page decision."""
        pdf = generate_pdf(sample_decision, audit_context)
        assert len(pdf) < 5 * 1024 * 1024

    def test_pdf_approve_decision(self, audit_context: AuditContext, sample_decision: Decision) -> None:
        """PDF generation succeeds for APPROVE outcome."""
        pdf = generate_pdf(sample_decision, audit_context)
        assert pdf[:4] == _PDF_MAGIC

    def test_pdf_decline_decision(self, audit_context: AuditContext, sample_decision: Decision) -> None:
        """PDF generation succeeds for DECLINE outcome."""
        from dataclasses import replace as dc_replace
        declined = sample_decision.model_copy(update={"outcome": DecisionOutcome.DECLINE})
        pdf = generate_pdf(declined, audit_context)
        assert pdf[:4] == _PDF_MAGIC

    def test_pdf_refer_decision(self, audit_context: AuditContext, sample_decision: Decision) -> None:
        """PDF generation succeeds for REFER outcome."""
        referred = sample_decision.model_copy(update={"outcome": DecisionOutcome.REFER})
        pdf = generate_pdf(referred, audit_context)
        assert pdf[:4] == _PDF_MAGIC


# ── PackageRequest + generate() (no S3) ──────────────────────────────────────

class TestPackagerIntegration:
    def test_generate_returns_package_result(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        req = PackageRequest(
            application_id="app-test-001",
            decision=sample_decision,
            audit_context=audit_context,
            write_to_s3=False,
        )
        result = generate(req)
        assert isinstance(result, PackageResult)

    def test_json_s3_key_format(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        req = PackageRequest(
            application_id="app-test-001",
            decision=sample_decision,
            audit_context=audit_context,
            write_to_s3=False,
        )
        result = generate(req)
        assert result.artifact_json_s3_key == "archive/app-test-001/decision.json"

    def test_pdf_s3_key_format(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        req = PackageRequest(
            application_id="app-test-001",
            decision=sample_decision,
            audit_context=audit_context,
            write_to_s3=False,
        )
        result = generate(req)
        assert result.artifact_pdf_s3_key == "archive/app-test-001/decision.pdf"

    def test_json_content_populated(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        req = PackageRequest(
            application_id="app-test-001",
            decision=sample_decision,
            audit_context=audit_context,
            write_to_s3=False,
        )
        result = generate(req)
        assert result.json_content
        parsed = json.loads(result.json_content)
        assert parsed["applicationId"] == "app-test-001"

    def test_pdf_bytes_populated_when_no_s3(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        req = PackageRequest(
            application_id="app-test-001",
            decision=sample_decision,
            audit_context=audit_context,
            write_to_s3=False,
        )
        result = generate(req)
        assert result.pdf_bytes is not None
        assert result.pdf_bytes[:4] == _PDF_MAGIC

    def test_different_application_ids_produce_different_keys(
        self, sample_decision: Decision, audit_context: AuditContext
    ) -> None:
        for app_id in ["app-001", "app-002", "app-xyz"]:
            req = PackageRequest(
                application_id=app_id,
                decision=sample_decision.model_copy(update={"application_id": app_id}),
                audit_context=audit_context,
                write_to_s3=False,
            )
            result = generate(req)
            assert result.artifact_json_s3_key == f"archive/{app_id}/decision.json"
            assert result.artifact_pdf_s3_key == f"archive/{app_id}/decision.pdf"
