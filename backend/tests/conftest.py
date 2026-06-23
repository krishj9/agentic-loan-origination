"""Shared pytest fixtures for backend tests.

Provides:
  - test_settings: Settings with safe defaults (no real AWS/Cognito).
  - test_user:     A CurrentUser with LoanOfficer role.
  - operator_user: A CurrentUser with Operator role.
  - client:        TestClient with auth + settings overrides applied.

Dependency overrides allow tests to run entirely in-process without
any cloud or network dependencies.
"""

from decimal import Decimal
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.core.auth import CurrentUser, get_current_user
from backend.core.deps import (
    get_application_service,
    get_document_service,
    get_runtime_client,
    get_s3_repository,
    get_settings,
    get_submission_service,
)
from backend.core.settings import Settings
from backend.main import create_app
from backend.repositories.s3_repository import S3Repository
from backend.services.application_service import ApplicationService


# ── Settings fixture ──────────────────────────────────────────────────────────


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings object with safe test defaults."""
    return Settings(
        app_env="test",
        log_level="DEBUG",
        runtime_mode="local",
        aws_region="us-east-1",
        s3_bucket_name="test-bucket",
        cognito_user_pool_id="us-east-1_TEST",
        cognito_client_id="test-client-id",
    )


# ── User fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def test_user() -> CurrentUser:
    """Authenticated LoanOfficer user."""
    return CurrentUser(sub="sub-loan-officer", username="loan.officer", groups=["LoanOfficer"])


@pytest.fixture
def operator_user() -> CurrentUser:
    """Authenticated Operator user."""
    return CurrentUser(sub="sub-operator", username="operator", groups=["Operator"])


# ── Mock S3 repository ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_s3() -> MagicMock:
    """S3Repository mock with all async methods pre-patched."""
    s3 = MagicMock(spec=S3Repository)
    s3.put_json = AsyncMock(return_value=None)
    s3.get_json = AsyncMock(return_value=None)
    s3.generate_presigned_put = AsyncMock(return_value="https://s3.example.com/presigned")
    s3.key_exists = AsyncMock(return_value=False)
    return s3


# ── Test client with overrides ────────────────────────────────────────────────


@pytest.fixture
def client(test_settings: Settings, test_user: CurrentUser, mock_s3: MagicMock) -> Generator[TestClient, None, None]:
    """TestClient with settings, auth, and S3 dependencies overridden."""
    app = create_app(test_settings)

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_s3_repository] = lambda: mock_s3

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc

    app.dependency_overrides.clear()


# ── Canonical test application payload ────────────────────────────────────────


@pytest.fixture
def create_payload() -> dict:
    """Valid CreateApplicationRequest body."""
    return {
        "applicantName": "Jane Smith",
        "annualIncome": "85000.00",
        "requestedLoanAmount": "20000.00",
        "debtUtilization": "0.25",
    }
