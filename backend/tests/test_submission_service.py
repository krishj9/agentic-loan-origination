"""Unit tests for SubmissionService.

Tests cover:
  - Happy path: transitions to PROCESSING, session ID assigned.
  - 409 when already submitted.
  - 422 when required documents are missing.
  - 422 when only one of the two required documents is present.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.clients.runtime_client import LocalRuntimeClient
from backend.core.settings import Settings
from backend.services.application_service import ApplicationService
from backend.services.submission_service import SubmissionService
from shared.schemas import ApplicationStatus, CanonicalApplication, Document, DocumentType


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_doc(doc_type: DocumentType, app_id: str = "app_test") -> Document:
    return Document(
        document_id=f"doc_{doc_type}",
        application_id=app_id,
        document_type=doc_type,
        s3_key=f"incoming/{app_id}/doc_{doc_type}.pdf",
        uploaded_at=datetime.now(UTC),
        parse_status="PENDING",
    )


def _make_app(
    status: ApplicationStatus = ApplicationStatus.PENDING,
    doc_types: list[DocumentType] | None = None,
) -> CanonicalApplication:
    app = CanonicalApplication(
        **{
            "applicationId": "app_test",
            "userId": "user-1",
            "applicantName": "Jane Smith",
            "annualIncome": Decimal("85000"),
            "requestedLoanAmount": Decimal("20000"),
            "debtUtilization": Decimal("0.25"),
            "status": status,
        }
    )
    if doc_types:
        app.document_inventory = [_make_doc(dt) for dt in doc_types]
    return app


_FULL_DOCS = [DocumentType.PAYSTUB, DocumentType.BANK_STATEMENT]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_app_svc() -> MagicMock:
    svc = MagicMock(spec=ApplicationService)
    svc.get_application = AsyncMock(return_value=_make_app(doc_types=_FULL_DOCS))
    svc.update_application = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        runtime_mode="local",
        cognito_user_pool_id="us-east-1_TEST",
        cognito_client_id="test-client",
    )


@pytest.fixture
def service(mock_app_svc: MagicMock, settings: Settings) -> SubmissionService:
    return SubmissionService(mock_app_svc, LocalRuntimeClient(), settings)


# ── Happy path ────────────────────────────────────────────────────────────────


async def test_submit_transitions_status_to_processing(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    result = await service.submit_application("app_test")
    assert result.status == ApplicationStatus.PROCESSING


async def test_submit_assigns_local_session_id(
    service: SubmissionService,
) -> None:
    result = await service.submit_application("app_test")
    assert result.runtime_session_id is not None
    assert result.runtime_session_id.startswith("local-")


async def test_submit_persists_updated_application(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    await service.submit_application("app_test")
    mock_app_svc.update_application.assert_called_once()
    updated_app: CanonicalApplication = mock_app_svc.update_application.call_args[0][0]
    assert updated_app.status == ApplicationStatus.PROCESSING


async def test_submit_stores_session_id_in_audit_context(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    result = await service.submit_application("app_test")
    updated_app: CanonicalApplication = mock_app_svc.update_application.call_args[0][0]
    assert updated_app.audit_context is not None
    assert updated_app.audit_context.runtime_session_id == result.runtime_session_id


async def test_submit_returns_helpful_message(service: SubmissionService) -> None:
    result = await service.submit_application("app_test")
    assert "processing" in result.message.lower() or "submitted" in result.message.lower()


# ── Error: already submitted ──────────────────────────────────────────────────


async def test_submit_raises_409_when_already_processing(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app(
        status=ApplicationStatus.PROCESSING,
        doc_types=_FULL_DOCS,
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_application("app_test")
    assert exc_info.value.status_code == 409


async def test_submit_raises_409_when_completed(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app(
        status=ApplicationStatus.COMPLETED,
        doc_types=_FULL_DOCS,
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_application("app_test")
    assert exc_info.value.status_code == 409


# ── Error: missing documents ──────────────────────────────────────────────────


async def test_submit_raises_422_when_no_documents(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app()  # no docs
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_application("app_test")
    assert exc_info.value.status_code == 422


async def test_submit_raises_422_when_only_paystub(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app(doc_types=[DocumentType.PAYSTUB])
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_application("app_test")
    assert exc_info.value.status_code == 422


async def test_submit_raises_422_when_only_bank_statement(
    service: SubmissionService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app(doc_types=[DocumentType.BANK_STATEMENT])
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_application("app_test")
    assert exc_info.value.status_code == 422
