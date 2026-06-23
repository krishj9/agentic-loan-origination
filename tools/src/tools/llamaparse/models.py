"""Pydantic v2 models for the LlamaParse tool contract (design §6.2).

These models are the stable interface between the document-extraction
subgraph and the LlamaParse implementation.  They match the Gateway tool
specification in ``agents.tools.schemas.LLAMAPARSE_TOOL_SPEC``.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas import DocumentType


class LlamaParseRequest(BaseModel):
    """Input contract for ``llamaparse.parse_financial_pdf``."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Application identifier for correlation.")
    document_id: str = Field(description="Document identifier within the application.")
    document_type: DocumentType = Field(description="Document class driving the parse profile.")
    s3_key: str = Field(description="Full S3 key under incoming/{application_id}/.")
    parse_profile: str = Field(
        default="auto",
        description="Named parse profile (e.g. 'paystub_v1', 'bank_statement_v1').",
    )


class LlamaParseRawOutput(BaseModel):
    """Intermediate model holding the raw LlamaParse API output before normalization."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(description="LlamaParse job identifier for audit trail.")
    raw_markdown: str = Field(description="Full document text rendered as Markdown by LlamaParse.")
    pages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-page extraction results from the LlamaParse job.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Job-level metadata returned by LlamaParse.",
    )


class LlamaParseResponse(BaseModel):
    """Output contract for ``llamaparse.parse_financial_pdf`` (design §6.2)."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Mirrors the request application_id.")
    document_id: str = Field(description="Mirrors the request document_id.")
    document_type: DocumentType = Field(description="Mirrors the request document_type.")
    raw_markdown: str = Field(description="Full document text rendered as Markdown by LlamaParse.")
    structured_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value extraction produced by the normalization layer.",
    )
    table_rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tabular rows extracted from the document (e.g. transaction table).",
    )
    confidence_notes: list[str] = Field(
        default_factory=list,
        description="Parser confidence notes or extraction warnings.",
    )
    document_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level metadata (page count, format, extraction timestamp).",
    )
