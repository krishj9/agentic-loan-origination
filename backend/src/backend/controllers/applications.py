"""Application API router: thin controller layer.

Controllers delegate all business logic to services (backend rule).
Every route:
  - Sets a response_model for OpenAPI accuracy.
  - Enforces authentication via RequireLoanOfficer / RequireAnyRole.
  - Binds the application_id to the logging context for CloudWatch correlation.

Endpoints (P2-T5 through P2-T8):
  POST /applications                      – create application
  POST /applications/{id}/documents       – get presigned upload URL
  POST /applications/{id}/submit          – trigger runtime session
  GET  /applications/{id}                 – get application status
  GET  /applications/{id}/decision        – get decision result
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from shared.schemas import Decision

from backend.core.auth import CurrentUser, RequireAnyRole, RequireLoanOfficer
from backend.core.deps import (
    ApplicationServiceDep,
    DocumentServiceDep,
    S3Dep,
    SubmissionServiceDep,
)
from backend.core.logging import set_application_id
from backend.schemas.application_schema import (
    ApplicationResponse,
    CreateApplicationRequest,
    DecisionResponse,
    DocumentUploadRequest,
    PresignedUploadResponse,
    SubmitApplicationResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])

_ApplicationIdPath = Annotated[str, Path(description="Unique application identifier.")]


# ── P2-T5: Create application ─────────────────────────────────────────────────


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationResponse,
    summary="Create a new loan application",
    responses={401: {"description": "Unauthenticated"}, 403: {"description": "Insufficient permissions"}},
)
async def create_application(
    body: CreateApplicationRequest,
    app_svc: ApplicationServiceDep,
    user: Annotated[CurrentUser, RequireLoanOfficer],
) -> ApplicationResponse:
    """Create a new loan application and return its ID."""
    return await app_svc.create_application(body, user)


# ── P2-T6: Presigned document upload URL ──────────────────────────────────────


@router.post(
    "/{application_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=PresignedUploadResponse,
    summary="Get a presigned S3 URL to upload a document",
    responses={
        404: {"description": "Application not found"},
        409: {"description": "Application not in uploadable state"},
    },
)
async def create_document_upload_url(
    application_id: _ApplicationIdPath,
    body: DocumentUploadRequest,
    doc_svc: DocumentServiceDep,
    user: Annotated[CurrentUser, RequireLoanOfficer],
) -> PresignedUploadResponse:
    """Issue a presigned S3 PUT URL scoped to the given document type."""
    set_application_id(application_id)
    return await doc_svc.create_presigned_upload(application_id, body)


# ── P2-T7: Submit application ─────────────────────────────────────────────────


@router.post(
    "/{application_id}/submit",
    response_model=SubmitApplicationResponse,
    summary="Submit the application to the agent runtime for processing",
    responses={
        404: {"description": "Application not found"},
        409: {"description": "Application already submitted"},
        422: {"description": "Required documents missing"},
    },
)
async def submit_application(
    application_id: _ApplicationIdPath,
    sub_svc: SubmissionServiceDep,
    user: Annotated[CurrentUser, RequireLoanOfficer],
) -> SubmitApplicationResponse:
    """Validate document completeness and start an AgentCore Runtime session."""
    set_application_id(application_id)
    return await sub_svc.submit_application(application_id)


# ── P2-T8: Status retrieval ───────────────────────────────────────────────────


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get the current status of a loan application",
    responses={404: {"description": "Application not found"}},
)
async def get_application_status(
    application_id: _ApplicationIdPath,
    app_svc: ApplicationServiceDep,
    user: Annotated[CurrentUser, RequireAnyRole],
) -> ApplicationResponse:
    """Return the application's current status, document count, and session ID."""
    set_application_id(application_id)
    app = await app_svc.get_application(application_id)
    return app_svc.to_response(app)


# ── P2-T8: Decision retrieval ─────────────────────────────────────────────────


@router.get(
    "/{application_id}/decision",
    response_model=DecisionResponse,
    summary="Retrieve the underwriting decision for a completed application",
    responses={
        404: {"description": "Decision not yet available or application not found"},
    },
)
async def get_decision(
    application_id: _ApplicationIdPath,
    s3: S3Dep,
    user: Annotated[CurrentUser, RequireAnyRole],
) -> DecisionResponse:
    """Return the structured decision JSON written by the packaging subgraph."""
    set_application_id(application_id)
    decision_key = f"archive/{application_id}/decision.json"
    data = await s3.get_json(decision_key)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Decision for application '{application_id}' is not yet available.",
        )

    decision = Decision(**data)
    return DecisionResponse(
        **{
            "applicationId": decision.application_id,
            "outcome": decision.outcome,
            "riskProfile": decision.risk_profile,
            "creditScore": decision.credit_score,
            "rationale": decision.rationale,
            "artifactJsonS3Key": decision.artifact_json_s3_key,
            "artifactPdfS3Key": decision.artifact_pdf_s3_key,
        }
    )
