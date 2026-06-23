"""Packaging tool interface — ``packaging.generate_artifacts`` (P3-T10).

Defines the Pydantic v2 request/response wrappers and the callable invoked
by the packaging subgraph.  Delegates to the Phase 4 packager
(``agents.tools.packager``) when available; falls back to a stub that
produces in-memory JSON/text artifacts and fake S3 keys for offline tests.

The stub never writes to S3 — it returns deterministic key strings that
the graph can store in state; the Phase 4 implementation performs the
actual S3 upload with KMS-encrypted, audit-metadata-enriched objects.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas import AuditContext, Decision

# ── Request / Response models ───────────────────────────────────────────────

class PackagingToolRequest(BaseModel):
    """Input contract for ``packaging.generate_artifacts``."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Application identifier (used to derive S3 prefix).")
    decision: Decision = Field(description="Final decision object from the make_decision node.")
    audit_context: AuditContext = Field(description="Audit envelope to embed in both artifacts.")
    s3_bucket: str = Field(
        default_factory=lambda: os.environ.get("S3_BUCKET_NAME", "loan-origination-documents-demo"),
        description="Target S3 bucket name.",
    )


class PackagingToolResponse(BaseModel):
    """Output contract for ``packaging.generate_artifacts``."""

    model_config = ConfigDict(populate_by_name=True)

    artifact_json_s3_key: str = Field(
        description="S3 key of the archived machine-readable decision JSON.",
    )
    artifact_pdf_s3_key: str = Field(
        description="S3 key of the archived human-readable decision PDF.",
    )
    json_content: str | None = Field(
        default=None,
        description="Serialised JSON content (non-None when using the stub).",
    )


# ── Key helpers ─────────────────────────────────────────────────────────────

def _json_key(application_id: str) -> str:
    return f"archive/{application_id}/decision.json"


def _pdf_key(application_id: str) -> str:
    return f"archive/{application_id}/decision.pdf"


# ── Stub implementation ─────────────────────────────────────────────────────

def _stub_package(request: PackagingToolRequest) -> PackagingToolResponse:
    """Build artifact keys and serialize the decision JSON in-memory."""
    artifact: dict[str, Any] = {
        **request.decision.model_dump(mode="json"),
        "audit_context": request.audit_context.model_dump(mode="json"),
    }
    json_content = json.dumps(artifact, indent=2, default=str)
    return PackagingToolResponse(
        artifact_json_s3_key=_json_key(request.application_id),
        artifact_pdf_s3_key=_pdf_key(request.application_id),
        json_content=json_content,
    )


def call_packaging(request: PackagingToolRequest) -> PackagingToolResponse:
    """Generate and archive decision artifacts.

    Delegates to the Phase 4 packager (``tools.packager.generate``)
    when available; uses the deterministic stub otherwise.

    Args:
        request: Validated ``PackagingToolRequest`` with decision and audit context.

    Returns:
        ``PackagingToolResponse`` with S3 artifact keys.
    """
    try:
        from tools.packager import PackageRequest, generate  # Phase 4

        pkg_req = PackageRequest(
            application_id=request.application_id,
            decision=request.decision,
            audit_context=request.audit_context,
            s3_bucket=request.s3_bucket,
        )
        pkg_result = generate(pkg_req)
        return PackagingToolResponse(
            artifact_json_s3_key=pkg_result.artifact_json_s3_key,
            artifact_pdf_s3_key=pkg_result.artifact_pdf_s3_key,
            json_content=pkg_result.json_content,
        )
    except ImportError:
        return _stub_package(request)


def get_tool_spec() -> dict[str, Any] | None:
    """Return the Gateway tool specification for this tool."""
    from agents.tools.schemas import PACKAGING_TOOL_SPEC

    return PACKAGING_TOOL_SPEC
