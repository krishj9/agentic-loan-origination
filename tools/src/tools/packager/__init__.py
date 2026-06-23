"""Artifact packager package — ``tools.packager.generate`` (P4-T6/T7).

Public interface::

    from tools.packager import generate, PackageRequest, PackageResult

    result = generate(
        PackageRequest(
            application_id="app_001",
            decision=decision,
            audit_context=audit,
            s3_bucket="my-bucket",
        )
    )
    # result.artifact_json_s3_key  → "archive/app_001/decision.json"
    # result.artifact_pdf_s3_key   → "archive/app_001/decision.pdf"
    # result.json_content          → serialized JSON string
"""

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas import AuditContext, Decision
from tools.log import get_logger
from tools.packager.generator import generate_json, generate_pdf

log = get_logger("packager")


class PackageRequest(BaseModel):
    """Input contract for the packager tool."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Application identifier — used to derive S3 prefix.")
    decision: Decision = Field(description="Final decision object from the make_decision node.")
    audit_context: AuditContext = Field(description="Audit envelope to embed in both artifacts.")
    s3_bucket: str = Field(
        default_factory=lambda: os.environ.get("S3_BUCKET_NAME", "loan-origination-documents-demo"),
        description="Target S3 bucket name.",
    )
    kms_key_id: str | None = Field(
        default=None,
        description="KMS key ARN/alias for SSE-KMS. Defaults to SSE-S3 when absent.",
    )
    write_to_s3: bool = Field(
        default=True,
        description=(
            "When True, artifacts are written to S3.  "
            "Set False in unit tests / offline use to skip S3 I/O."
        ),
    )


class PackageResult(BaseModel):
    """Output contract for the packager tool."""

    model_config = ConfigDict(populate_by_name=True)

    artifact_json_s3_key: str = Field(
        description="S3 key of the archived machine-readable decision JSON.",
    )
    artifact_pdf_s3_key: str = Field(
        description="S3 key of the archived human-readable decision PDF.",
    )
    json_content: str = Field(
        description="Serialised JSON content (always populated for audit/testing).",
    )
    pdf_bytes: bytes | None = Field(
        default=None,
        description="Generated PDF bytes (populated when write_to_s3=False for testing).",
    )


def generate(request: PackageRequest) -> PackageResult:
    """Generate decision artifacts and optionally archive them to S3 (P4-T6/T7).

    Steps:
      1. Generate JSON payload using :func:`tools.packager.generator.generate_json`.
      2. Generate PDF using :func:`tools.packager.generator.generate_pdf`.
      3. If ``write_to_s3`` is True: write both artifacts to S3 via archive module.

    Args:
        request: Validated :class:`PackageRequest`.

    Returns:
        :class:`PackageResult` with S3 artifact keys and the JSON content string.
    """
    ctx: dict[str, Any] = {"application_id": request.application_id}
    log.info("generating decision artifacts", correlation=ctx)

    json_key = f"archive/{request.application_id}/decision.json"
    pdf_key = f"archive/{request.application_id}/decision.pdf"

    json_content = generate_json(request.decision, request.audit_context)
    pdf_bytes = generate_pdf(request.decision, request.audit_context)

    log.info(
        "artifacts generated",
        correlation=ctx,
        json_bytes=len(json_content),
        pdf_bytes=len(pdf_bytes),
    )

    if request.write_to_s3:
        from tools.packager.archive import put_json, put_pdf

        json_key = put_json(
            request.application_id,
            json_content,
            request.audit_context,
            bucket=request.s3_bucket,
            kms_key_id=request.kms_key_id,
        )
        pdf_key = put_pdf(
            request.application_id,
            pdf_bytes,
            request.audit_context,
            bucket=request.s3_bucket,
            kms_key_id=request.kms_key_id,
        )

    return PackageResult(
        artifact_json_s3_key=json_key,
        artifact_pdf_s3_key=pdf_key,
        json_content=json_content,
        pdf_bytes=pdf_bytes if not request.write_to_s3 else None,
    )


__all__ = ["PackageRequest", "PackageResult", "generate"]
