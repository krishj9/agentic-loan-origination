"""HTTP-layer request/response schemas for the application API.

These models wrap the canonical shared types (shared.schemas) with
HTTP-specific concerns: strict input validation, camelCase aliases,
and OpenAPI examples.

Convention:
  - *Request  models are used for request body validation.
  - *Response models carry response_model annotations in controllers.
  - ErrorResponse is the stable error envelope (org comms rule).

Fields that appear in both requests and shared schemas delegate to the
canonical type rather than duplicating validation rules.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas.enums import ApplicationStatus, DecisionOutcome, DocumentType, RiskProfile


class CreateApplicationRequest(BaseModel):
    """Request body for POST /applications.

    All monetary values use Decimal to preserve precision through JSON
    serialisation and into the risk engine.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicantName": "Jane Smith",
                "annualIncome": "85000.00",
                "requestedLoanAmount": "20000.00",
                "debtUtilization": "0.25",
            }
        },
    )

    applicant_name: str = Field(
        alias="applicantName",
        min_length=1,
        max_length=200,
        description="Full legal name of the loan applicant.",
    )
    annual_income: Decimal = Field(
        alias="annualIncome",
        gt=0,
        description="Annualised gross income (USD).",
    )
    requested_loan_amount: Decimal = Field(
        alias="requestedLoanAmount",
        gt=0,
        description="Amount requested (USD).",
    )
    debt_utilization: Decimal = Field(
        alias="debtUtilization",
        ge=0,
        le=1,
        description="Aggregate debt utilisation ratio (0.0 – 1.0).",
    )


class ApplicationResponse(BaseModel):
    """Response for application resource endpoints (POST /applications, GET /applications/{id})."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(alias="applicationId", description="Unique application identifier.")
    status: ApplicationStatus = Field(description="Current lifecycle status.")
    applicant_name: str = Field(alias="applicantName")
    annual_income: Decimal = Field(alias="annualIncome")
    requested_loan_amount: Decimal = Field(alias="requestedLoanAmount")
    debt_utilization: Decimal = Field(alias="debtUtilization")
    document_count: int = Field(alias="documentCount", default=0)
    runtime_session_id: str | None = Field(
        alias="runtimeSessionId",
        default=None,
        description="AgentCore Runtime session ID, populated after submission.",
    )


class DocumentUploadRequest(BaseModel):
    """Request body for POST /applications/{id}/documents."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {"documentType": "PAYSTUB"}},
    )

    document_type: DocumentType = Field(
        alias="documentType",
        description="Document class determines the LlamaParse parse profile.",
    )


class PresignedUploadResponse(BaseModel):
    """Presigned S3 PUT URL response (P2-T6).

    The client must PUT the file bytes directly to `uploadUrl` using the
    Content-Type specified in `contentType`.  The URL expires after
    `expiresInSeconds` seconds.
    """

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(alias="documentId", description="Assigned document identifier.")
    upload_url: str = Field(alias="uploadUrl", description="Presigned S3 PUT URL.")
    s3_key: str = Field(alias="s3Key", description="S3 object key the file will be written to.")
    content_type: str = Field(
        alias="contentType",
        default="application/pdf",
        description="Content-Type the client must set when uploading.",
    )
    expires_in_seconds: int = Field(alias="expiresInSeconds", description="Seconds until the URL expires.")


class SubmitApplicationResponse(BaseModel):
    """Response for POST /applications/{id}/submit."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(alias="applicationId")
    status: ApplicationStatus = Field(description="New status after submission (PROCESSING).")
    runtime_session_id: str | None = Field(
        alias="runtimeSessionId",
        default=None,
        description="AgentCore Runtime session ID for cross-log correlation.",
    )
    message: str = Field(description="Human-readable status message.")


class DecisionResponse(BaseModel):
    """Response for GET /applications/{id}/decision.

    Surfaces the canonical Decision fields without nesting the full
    risk-engine and compliance sub-objects (those are available in the
    raw S3 artifact for auditors).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicationId": "app_abc123",
                "outcome": "APPROVE",
                "riskProfile": "PRIME",
                "creditScore": 745,
                "rationale": "Income band HIGH, utilization band LOW. No compliance flags triggered.",
                "artifactJsonS3Key": "archive/app_abc123/decision.json",
                "artifactPdfS3Key": "archive/app_abc123/decision.pdf",
            }
        },
    )

    application_id: str = Field(alias="applicationId")
    outcome: DecisionOutcome
    risk_profile: RiskProfile = Field(alias="riskProfile")
    credit_score: int = Field(alias="creditScore")
    rationale: str
    artifact_json_s3_key: str | None = Field(alias="artifactJsonS3Key", default=None)
    artifact_pdf_s3_key: str | None = Field(alias="artifactPdfS3Key", default=None)


class ErrorResponse(BaseModel):
    """Stable error envelope returned for all 4xx and 5xx responses.

    Org comms rule: consistent error shape with stable codes; no stack
    traces or internal details exposed to callers.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "errorCode": "HTTP_404",
                "message": "Application 'app_xyz' not found.",
                "traceId": "550e8400-e29b-41d4-a716-446655440000",
            }
        },
    )

    error_code: str = Field(
        alias="errorCode",
        description="Stable machine-readable error code (e.g. HTTP_404, VALIDATION_ERROR).",
    )
    message: str = Field(description="Safe, user-facing error message. No internal stack traces.")
    trace_id: str | None = Field(
        alias="traceId",
        default=None,
        description="Trace ID for correlating this error with server-side logs.",
    )
