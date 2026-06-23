"""Unit tests for DocumentService.

Tests cover:
  - create_presigned_upload: happy path, URL returned, inventory updated.
  - Rejection when application status is not PENDING (409).
  - S3 key follows the incoming/{app_id}/{doc_id}.pdf pattern.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.settings import Settings
from backend.repositories.s3_repository import S3Repository
from backend.schemas.application_schema import DocumentUploadRequest
from backend.services.application_service import ApplicationService
from backend.services.document_service import DocumentService
from shared.schemas import ApplicationStatus, CanonicalApplication, DocumentType


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app(status: ApplicationStatus = ApplicationStatus.PENDING) -> CanonicalApplication:
    return CanonicalApplication(
        **{
            "applicationId": "app_abc123",
            "userId": "user-1",
            "applicantName": "Jane Smith",
            "annualIncome": Decimal("85000"),
            "requestedLoanAmount": Decimal("20000"),
            "debtUtilization": Decimal("0.25"),
            "status": status,
        }
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_s3() -> MagicMock:
    s3 = MagicMock(spec=S3Repository)
    s3.generate_presigned_put = AsyncMock(return_value="https://s3.example.com/presigned")
    s3.put_json = AsyncMock(return_value=None)
    return s3


@pytest.fixture
def mock_app_svc() -> MagicMock:
    svc = MagicMock(spec=ApplicationService)
    svc.get_application = AsyncMock(return_value=_make_app())
    svc.update_application = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        s3_bucket_name="test-bucket",
        presigned_url_ttl_seconds=900,
        cognito_user_pool_id="us-east-1_TEST",
        cognito_client_id="test-client",
    )


@pytest.fixture
def service(mock_s3: MagicMock, mock_app_svc: MagicMock, settings: Settings) -> DocumentService:
    return DocumentService(mock_s3, mock_app_svc, settings)


# ── Happy path ────────────────────────────────────────────────────────────────


async def test_create_presigned_upload_returns_url(
    service: DocumentService,
    mock_s3: MagicMock,
) -> None:
    req = DocumentUploadRequest(**{"documentType": DocumentType.PAYSTUB})
    resp = await service.create_presigned_upload("app_abc123", req)
    assert resp.upload_url == "https://s3.example.com/presigned"


async def test_create_presigned_upload_returns_correct_expiry(
    service: DocumentService,
) -> None:
    req = DocumentUploadRequest(**{"documentType": DocumentType.PAYSTUB})
    resp = await service.create_presigned_upload("app_abc123", req)
    assert resp.expires_in_seconds == 900


async def test_create_presigned_upload_s3_key_contains_application_id(
    service: DocumentService,
) -> None:
    req = DocumentUploadRequest(**{"documentType": DocumentType.BANK_STATEMENT})
    resp = await service.create_presigned_upload("app_abc123", req)
    assert "app_abc123" in resp.s3_key
    assert resp.s3_key.startswith("incoming/")
    assert resp.s3_key.endswith(".pdf")


async def test_create_presigned_upload_document_id_prefixed_doc(
    service: DocumentService,
) -> None:
    req = DocumentUploadRequest(**{"documentType": DocumentType.PAYSTUB})
    resp = await service.create_presigned_upload("app_abc123", req)
    assert resp.document_id.startswith("doc_")


async def test_create_presigned_upload_updates_inventory(
    service: DocumentService,
    mock_app_svc: MagicMock,
) -> None:
    req = DocumentUploadRequest(**{"documentType": DocumentType.PAYSTUB})
    await service.create_presigned_upload("app_abc123", req)
    mock_app_svc.update_application.assert_called_once()
    updated_app: CanonicalApplication = mock_app_svc.update_application.call_args[0][0]
    assert len(updated_app.document_inventory) == 1
    assert updated_app.document_inventory[0].document_type == DocumentType.PAYSTUB


# ── Error cases ───────────────────────────────────────────────────────────────


async def test_create_presigned_upload_rejects_processing_status(
    service: DocumentService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app(ApplicationStatus.PROCESSING)
    req = DocumentUploadRequest(**{"documentType": DocumentType.PAYSTUB})
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.create_presigned_upload("app_abc123", req)
    assert exc_info.value.status_code == 409


async def test_create_presigned_upload_rejects_completed_status(
    service: DocumentService,
    mock_app_svc: MagicMock,
) -> None:
    mock_app_svc.get_application.return_value = _make_app(ApplicationStatus.COMPLETED)
    req = DocumentUploadRequest(**{"documentType": DocumentType.PAYSTUB})
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.create_presigned_upload("app_abc123", req)
    assert exc_info.value.status_code == 409
