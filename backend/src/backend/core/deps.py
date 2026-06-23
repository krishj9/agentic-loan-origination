"""FastAPI dependency-injection providers.

Declares factory functions for all shared infrastructure objects (Settings,
S3Repository, RuntimeClient) and service objects (ApplicationService,
DocumentService, SubmissionService).  Using Depends() here keeps controllers
thin and makes dependency overrides in tests straightforward.
"""

from typing import Annotated

from fastapi import Depends

from backend.core.settings import Settings, get_settings

# Re-export get_settings so callers can import it from either module
__all__ = ["get_settings"]

# ── Settings ──────────────────────────────────────────────────────────────────

SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Infrastructure ────────────────────────────────────────────────────────────


def get_s3_repository(settings: SettingsDep) -> "S3Repository":
    """Provide an S3Repository configured from application settings."""
    from backend.repositories.s3_repository import S3Repository

    return S3Repository(settings)


S3Dep = Annotated["S3Repository", Depends(get_s3_repository)]


def get_runtime_client(settings: SettingsDep) -> "RuntimeClient":
    """Provide the appropriate RuntimeClient based on RUNTIME_MODE."""
    from backend.clients.runtime_client import make_runtime_client

    return make_runtime_client(settings)


RuntimeClientDep = Annotated["RuntimeClient", Depends(get_runtime_client)]


# ── Services ──────────────────────────────────────────────────────────────────


def get_application_service(s3: S3Dep, settings: SettingsDep) -> "ApplicationService":
    """Provide an ApplicationService with injected S3Repository."""
    from backend.services.application_service import ApplicationService

    return ApplicationService(s3, settings)


ApplicationServiceDep = Annotated["ApplicationService", Depends(get_application_service)]


def get_document_service(
    s3: S3Dep,
    app_svc: ApplicationServiceDep,
    settings: SettingsDep,
) -> "DocumentService":
    """Provide a DocumentService with injected dependencies."""
    from backend.services.document_service import DocumentService

    return DocumentService(s3, app_svc, settings)


DocumentServiceDep = Annotated["DocumentService", Depends(get_document_service)]


def get_submission_service(
    app_svc: ApplicationServiceDep,
    runtime: RuntimeClientDep,
    settings: SettingsDep,
) -> "SubmissionService":
    """Provide a SubmissionService with injected dependencies."""
    from backend.services.submission_service import SubmissionService

    return SubmissionService(app_svc, runtime, settings)


SubmissionServiceDep = Annotated["SubmissionService", Depends(get_submission_service)]


# Forward-reference type aliases (avoid import-time circular deps)
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from backend.clients.runtime_client import RuntimeClient
    from backend.repositories.s3_repository import S3Repository
    from backend.services.application_service import ApplicationService
    from backend.services.document_service import DocumentService
    from backend.services.submission_service import SubmissionService
