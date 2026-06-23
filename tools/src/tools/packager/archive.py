"""S3 archival with audit metadata — ``tools.packager.archive`` (P4-T7).

Design §4.4 / §9.2: Writes both the JSON and PDF artifacts to
``archive/{application_id}/`` with:
  - KMS-encrypted server-side encryption (SSE-KMS or SSE-S3 as fallback).
  - TLS-only writes (enforced by bucket policy; client always uses HTTPS).
  - S3 object metadata embedding ``application_id``, ``user_id``,
    ``submission_timestamp``, ``decision_timestamp``, and ``runtime_session_id``.

All AWS exceptions are allowed to propagate — the caller (packaging subgraph)
handles errors and surfaces them through the graph state.
"""

import os

import boto3
from botocore.config import Config

from shared.schemas import AuditContext
from tools.log import get_logger

log = get_logger("packager.archive")

_DEFAULT_BUCKET = "loan-origination-documents-demo"
_DEFAULT_REGION = "us-east-1"
_BOTO_CONFIG = Config(
    region_name=os.environ.get("AWS_REGION", _DEFAULT_REGION),
)


def _s3_client() -> "boto3.client":
    return boto3.client("s3", config=_BOTO_CONFIG, use_ssl=True)


def _build_metadata(audit: AuditContext) -> dict[str, str]:
    """Build the S3 object metadata dict from the audit context.

    S3 metadata values must be strings; None values are omitted.
    """
    meta: dict[str, str] = {
        "application-id": audit.application_id,
        "user-id": audit.user_id,
        "submission-timestamp": audit.submission_timestamp.isoformat(),
    }
    if audit.decision_timestamp:
        meta["decision-timestamp"] = audit.decision_timestamp.isoformat()
    if audit.runtime_session_id:
        meta["runtime-session-id"] = audit.runtime_session_id
    if audit.trace_id:
        meta["trace-id"] = audit.trace_id
    return meta


def put_json(
    application_id: str,
    json_content: str,
    audit: AuditContext,
    bucket: str | None = None,
    kms_key_id: str | None = None,
) -> str:
    """Write the decision JSON artifact to S3.

    Args:
        application_id: Determines the ``archive/{application_id}/`` prefix.
        json_content: Serialised JSON string from :func:`tools.packager.generator.generate_json`.
        audit: Audit context for object metadata and structured logging.
        bucket: S3 bucket name (defaults to ``S3_BUCKET_NAME`` env var).
        kms_key_id: KMS key ARN/alias for SSE-KMS. If absent, uses SSE-S3.

    Returns:
        The S3 key of the written object.
    """
    s3_bucket = bucket or os.environ.get("S3_BUCKET_NAME", _DEFAULT_BUCKET)
    key = f"archive/{application_id}/decision.json"
    ctx = {"application_id": application_id}

    log.info("archiving decision JSON", correlation=ctx, s3_key=key, bucket=s3_bucket)

    put_kwargs: dict = {
        "Bucket": s3_bucket,
        "Key": key,
        "Body": json_content.encode("utf-8"),
        "ContentType": "application/json",
        "Metadata": _build_metadata(audit),
    }
    if kms_key_id:
        put_kwargs["ServerSideEncryption"] = "aws:kms"
        put_kwargs["SSEKMSKeyId"] = kms_key_id
    else:
        put_kwargs["ServerSideEncryption"] = "AES256"

    s3 = _s3_client()
    s3.put_object(**put_kwargs)

    log.info("decision JSON archived", correlation=ctx, s3_key=key)
    return key


def put_pdf(
    application_id: str,
    pdf_bytes: bytes,
    audit: AuditContext,
    bucket: str | None = None,
    kms_key_id: str | None = None,
) -> str:
    """Write the decision PDF artifact to S3.

    Args:
        application_id: Determines the ``archive/{application_id}/`` prefix.
        pdf_bytes: PDF bytes from :func:`tools.packager.generator.generate_pdf`.
        audit: Audit context for object metadata and structured logging.
        bucket: S3 bucket name (defaults to ``S3_BUCKET_NAME`` env var).
        kms_key_id: KMS key ARN/alias for SSE-KMS. If absent, uses SSE-S3.

    Returns:
        The S3 key of the written object.
    """
    s3_bucket = bucket or os.environ.get("S3_BUCKET_NAME", _DEFAULT_BUCKET)
    key = f"archive/{application_id}/decision.pdf"
    ctx = {"application_id": application_id}

    log.info("archiving decision PDF", correlation=ctx, s3_key=key, bucket=s3_bucket, bytes=len(pdf_bytes))

    put_kwargs: dict = {
        "Bucket": s3_bucket,
        "Key": key,
        "Body": pdf_bytes,
        "ContentType": "application/pdf",
        "Metadata": _build_metadata(audit),
    }
    if kms_key_id:
        put_kwargs["ServerSideEncryption"] = "aws:kms"
        put_kwargs["SSEKMSKeyId"] = kms_key_id
    else:
        put_kwargs["ServerSideEncryption"] = "AES256"

    s3 = _s3_client()
    s3.put_object(**put_kwargs)

    log.info("decision PDF archived", correlation=ctx, s3_key=key)
    return key
