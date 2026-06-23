"""Unit tests for ApplicationService.

Tests cover:
  - create_application: happy path, S3 persistence, response shape.
  - get_application: 404 on missing record, returns CanonicalApplication.
  - update_application: delegates to S3.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.auth import CurrentUser
from backend.core.settings import Settings
from backend.repositories.s3_repository import S3Repository
from backend.schemas.application_schema import CreateApplicationRequest
from backend.services.application_service import ApplicationService
from shared.schemas import ApplicationStatus, CanonicalApplication


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        runtime_mode="local",
        s3_bucket_name="test-bucket",
        cognito_user_pool_id="us-east-1_TEST",
        cognito_client_id="test-client",
    )


@pytest.fixture
def mock_s3() -> MagicMock:
    s3 = MagicMock(spec=S3Repository)
    s3.put_json = AsyncMock(return_value=None)
    s3.get_json = AsyncMock(return_value=None)
    return s3


@pytest.fixture
def service(mock_s3: MagicMock, settings: Settings) -> ApplicationService:
    return ApplicationService(mock_s3, settings)


@pytest.fixture
def loan_officer() -> CurrentUser:
    return CurrentUser(sub="sub-abc", username="loan.officer", groups=["LoanOfficer"])


@pytest.fixture
def create_request() -> CreateApplicationRequest:
    return CreateApplicationRequest(
        **{
            "applicantName": "Jane Smith",
            "annualIncome": Decimal("85000.00"),
            "requestedLoanAmount": Decimal("20000.00"),
            "debtUtilization": Decimal("0.25"),
        }
    )


def _sample_app_data(application_id: str = "app_abc123") -> dict:
    return {
        "applicationId": application_id,
        "userId": "sub-abc",
        "applicantName": "Jane Smith",
        "annualIncome": "85000.00",
        "requestedLoanAmount": "20000.00",
        "debtUtilization": "0.25",
        "status": "PENDING",
        "documentInventory": [],
        "auditContext": {
            "application_id": application_id,
            "user_id": "sub-abc",
            "submission_timestamp": "2026-06-22T18:00:00+00:00",
        },
    }


# ── create_application ────────────────────────────────────────────────────────


async def test_create_application_returns_pending_status(
    service: ApplicationService,
    loan_officer: CurrentUser,
    create_request: CreateApplicationRequest,
) -> None:
    result = await service.create_application(create_request, loan_officer)
    assert result.status == ApplicationStatus.PENDING


async def test_create_application_assigns_application_id(
    service: ApplicationService,
    loan_officer: CurrentUser,
    create_request: CreateApplicationRequest,
) -> None:
    result = await service.create_application(create_request, loan_officer)
    assert result.application_id.startswith("app_")
    assert len(result.application_id) > 5


async def test_create_application_returns_correct_financial_fields(
    service: ApplicationService,
    loan_officer: CurrentUser,
    create_request: CreateApplicationRequest,
) -> None:
    result = await service.create_application(create_request, loan_officer)
    assert result.applicant_name == "Jane Smith"
    assert result.annual_income == Decimal("85000.00")
    assert result.document_count == 0


async def test_create_application_persists_to_s3(
    service: ApplicationService,
    mock_s3: MagicMock,
    loan_officer: CurrentUser,
    create_request: CreateApplicationRequest,
) -> None:
    await service.create_application(create_request, loan_officer)
    mock_s3.put_json.assert_called_once()
    call_key: str = mock_s3.put_json.call_args[0][0]
    assert "incoming/" in call_key
    assert "application.json" in call_key


async def test_create_application_persists_correct_user_id(
    service: ApplicationService,
    mock_s3: MagicMock,
    loan_officer: CurrentUser,
    create_request: CreateApplicationRequest,
) -> None:
    await service.create_application(create_request, loan_officer)
    persisted_data: dict = mock_s3.put_json.call_args[0][1]
    assert persisted_data["userId"] == "sub-abc"
    assert persisted_data["status"] == "PENDING"


# ── get_application ───────────────────────────────────────────────────────────


async def test_get_application_raises_404_when_missing(
    service: ApplicationService, mock_s3: MagicMock
) -> None:
    mock_s3.get_json.return_value = None
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.get_application("app_nonexistent")
    assert exc_info.value.status_code == 404


async def test_get_application_returns_canonical_application(
    service: ApplicationService, mock_s3: MagicMock
) -> None:
    mock_s3.get_json.return_value = _sample_app_data()
    result = await service.get_application("app_abc123")
    assert isinstance(result, CanonicalApplication)
    assert result.application_id == "app_abc123"
    assert result.status == ApplicationStatus.PENDING


# ── update_application ────────────────────────────────────────────────────────


async def test_update_application_calls_s3_put(
    service: ApplicationService, mock_s3: MagicMock
) -> None:
    mock_s3.get_json.return_value = _sample_app_data()
    app = await service.get_application("app_abc123")
    app.status = ApplicationStatus.PROCESSING
    await service.update_application(app)
    assert mock_s3.put_json.call_count == 1
