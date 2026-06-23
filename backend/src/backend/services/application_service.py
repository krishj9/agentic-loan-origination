"""Application business logic: create, retrieve, and update loan applications.

Applications are persisted as JSON objects in S3 under the path:
  incoming/{application_id}/application.json

This layout is consistent with design §9.2 and allows Phase 4 document
extraction to write extracted artifacts alongside the application record.

Controllers must remain thin: all business logic lives in this service.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from shared.schemas import ApplicationStatus, AuditContext, CanonicalApplication

from backend.core.auth import CurrentUser
from backend.core.logging import set_application_id
from backend.core.settings import Settings
from backend.repositories.s3_repository import S3Repository
from backend.schemas.application_schema import ApplicationResponse, CreateApplicationRequest

log = logging.getLogger(__name__)

_APP_KEY_TEMPLATE = "incoming/{application_id}/application.json"


def _app_s3_key(application_id: str) -> str:
    return _APP_KEY_TEMPLATE.format(application_id=application_id)


class ApplicationService:
    """Manages the lifecycle of a loan application record in S3."""

    def __init__(self, s3: S3Repository, settings: Settings) -> None:
        self._s3 = s3
        self._settings = settings

    async def create_application(
        self,
        request: CreateApplicationRequest,
        user: CurrentUser,
    ) -> ApplicationResponse:
        """Create a new application, persist to S3, return the API response.

        Assigns a unique application_id, stamps submission_timestamp, and
        writes the canonical record to S3 before returning.

        Args:
            request: Validated creation payload.
            user:    Authenticated loan officer making the request.

        Returns:
            ApplicationResponse with the newly assigned application_id.
        """
        application_id = f"app_{uuid.uuid4().hex}"
        set_application_id(application_id)
        now = datetime.now(UTC)

        canonical = CanonicalApplication(
            **{
                "applicationId": application_id,
                "userId": user.sub,
                "applicantName": request.applicant_name,
                "annualIncome": request.annual_income,
                "requestedLoanAmount": request.requested_loan_amount,
                "debtUtilization": request.debt_utilization,
                "status": ApplicationStatus.PENDING,
                "documentInventory": [],
                "auditContext": AuditContext(
                    application_id=application_id,
                    user_id=user.sub,
                    submission_timestamp=now,
                ).model_dump(),
            }
        )

        await self._s3.put_json(
            _app_s3_key(application_id),
            canonical.model_dump(mode="json", by_alias=True),
        )

        log.info(
            "Application created",
            extra={
                "application_id": application_id,
                "user_id": user.sub,
                "requested_loan_amount": str(request.requested_loan_amount),
            },
        )

        return _to_response(canonical)

    async def get_application(self, application_id: str) -> CanonicalApplication:
        """Retrieve an application from S3.

        Raises:
            HTTPException(404): when the application does not exist.
        """
        data = await self._s3.get_json(_app_s3_key(application_id))
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Application '{application_id}' not found.",
            )
        return CanonicalApplication(**data)

    async def update_application(self, application: CanonicalApplication) -> None:
        """Persist a mutated CanonicalApplication back to S3."""
        await self._s3.put_json(
            _app_s3_key(application.application_id),
            application.model_dump(mode="json", by_alias=True),
        )
        log.debug(
            "Application updated",
            extra={
                "application_id": application.application_id,
                "status": str(application.status),
            },
        )

    def to_response(self, app: CanonicalApplication) -> ApplicationResponse:
        """Convert a CanonicalApplication to the HTTP response model."""
        return _to_response(app)


def _to_response(app: CanonicalApplication) -> ApplicationResponse:
    """Pure function: map a canonical application to the API response shape."""
    runtime_session_id: str | None = None
    if app.audit_context and app.audit_context.runtime_session_id:
        runtime_session_id = app.audit_context.runtime_session_id

    return ApplicationResponse(
        **{
            "applicationId": app.application_id,
            "status": app.status,
            "applicantName": app.applicant_name,
            "annualIncome": app.annual_income,
            "requestedLoanAmount": app.requested_loan_amount,
            "debtUtilization": app.debt_utilization,
            "documentCount": len(app.document_inventory),
            "runtimeSessionId": runtime_session_id,
        }
    )
