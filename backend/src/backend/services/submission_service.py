"""Application submission service: validates completeness and starts a runtime session.

A submission requires:
  1. The application must be in PENDING status.
  2. Both a PAYSTUB and a BANK_STATEMENT must be present in the inventory.

On success the application transitions to PROCESSING and the AgentCore
Runtime session ID is stored in audit_context.runtime_session_id for
cross-log correlation (design §10.1).

Org comms rule: transient failures in RuntimeClient are retried inside
the client (bounded retries + timeout); this service treats a start_session
call that raises as a hard error and re-raises to the caller.
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from shared.schemas import ApplicationStatus, AuditContext

from backend.clients.runtime_client import RuntimeClient
from backend.core.logging import set_application_id
from backend.core.settings import Settings
from backend.schemas.application_schema import SubmitApplicationResponse
from backend.services.application_service import ApplicationService

log = logging.getLogger(__name__)

_REQUIRED_DOC_TYPES = frozenset({"PAYSTUB", "BANK_STATEMENT"})


class SubmissionService:
    """Validates application completeness and delegates to the runtime client."""

    def __init__(
        self,
        application_service: ApplicationService,
        runtime_client: RuntimeClient,
        settings: Settings,
    ) -> None:
        self._app_svc = application_service
        self._runtime = runtime_client
        self._settings = settings

    async def submit_application(self, application_id: str) -> SubmitApplicationResponse:
        """Submit a complete application to the AgentCore Runtime.

        Steps:
          1. Load and validate the application (status + doc completeness).
          2. Start a Runtime session via RuntimeClient.
          3. Transition application status to PROCESSING and persist.
          4. Return the accepted-status response.

        Args:
            application_id: ID of the application to submit.

        Returns:
            SubmitApplicationResponse with PROCESSING status and session ID.

        Raises:
            HTTPException(404): application not found.
            HTTPException(409): application already submitted or in terminal state.
            HTTPException(422): required documents missing.
        """
        set_application_id(application_id)
        app = await self._app_svc.get_application(application_id)

        if app.status != ApplicationStatus.PENDING:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Application '{application_id}' is already in '{app.status}' status "
                    "and cannot be resubmitted."
                ),
            )

        uploaded_types = {str(doc.document_type) for doc in app.document_inventory}
        missing_types = _REQUIRED_DOC_TYPES - uploaded_types
        if missing_types:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required document types: {sorted(missing_types)}. "
                "Upload a PAYSTUB and a BANK_STATEMENT before submitting.",
            )

        payload = app.model_dump(mode="json", by_alias=True)
        session_id = await self._runtime.start_session(payload)

        if app.audit_context is None:
            app.audit_context = AuditContext(
                application_id=application_id,
                user_id="",
                submission_timestamp=datetime.now(UTC),
            )
        app.audit_context.runtime_session_id = session_id
        app.status = ApplicationStatus.PROCESSING

        await self._app_svc.update_application(app)

        log.info(
            "Application submitted to runtime",
            extra={
                "application_id": application_id,
                "runtime_session_id": session_id,
            },
        )

        return SubmitApplicationResponse(
            **{
                "applicationId": application_id,
                "status": ApplicationStatus.PROCESSING,
                "runtimeSessionId": session_id,
                "message": "Application submitted for processing. "
                "Poll GET /applications/{id} for status updates.",
            }
        )
