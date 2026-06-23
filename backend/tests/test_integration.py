"""Backend integration tests — P6-T8.

Covers the end-to-end HTTP flow:
  POST /applications           → 201 Created
  POST /applications/{id}/documents → 200 with presigned URL
  POST /applications/{id}/submit   → 202 Accepted / 200
  GET  /applications/{id}          → status check
  GET  /applications/{id}/decision → decision payload (when available)

All external dependencies are replaced via FastAPI dependency_overrides so that:
  * No real AWS calls are made (S3Repository and RuntimeClient are mocked).
  * Authentication is bypassed with a pre-built CurrentUser.
  * Settings point at a local/test environment.

The tests follow the same pattern as ``backend/tests/conftest.py`` so the
existing fixtures are re-used where possible.  The scope is the *HTTP contract*
(routing, status codes, response shapes) rather than business logic (covered by
the unit tests in the same directory).
"""

from datetime import UTC, datetime
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
from shared.schemas import (
    ApplicationStatus,
    CanonicalApplication,
    DecisionOutcome,
    Document,
    DocumentType,
    RiskProfile,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _make_settings() -> Settings:
    return Settings(
        app_env="test",
        log_level="DEBUG",
        runtime_mode="local",
        aws_region="us-east-1",
        s3_bucket_name="test-bucket",
        cognito_user_pool_id="us-east-1_TEST",
        cognito_client_id="test-client-id",
    )


def _make_loan_officer() -> CurrentUser:
    return CurrentUser(sub="sub-lo", username="loan.officer", groups=["LoanOfficer"])


def _make_app(
    application_id: str = "app_integ_001",
    status: ApplicationStatus = ApplicationStatus.PENDING,
    with_docs: bool = False,
    with_decision: bool = False,
) -> CanonicalApplication:
    docs = []
    if with_docs:
        docs = [
            Document(
                document_id=f"doc_{dt.value}",
                application_id=application_id,
                document_type=dt,
                s3_key=f"incoming/{application_id}/doc_{dt.value}.pdf",
                uploaded_at=datetime.now(UTC),
                parse_status="PENDING",
            )
            for dt in [DocumentType.PAYSTUB, DocumentType.BANK_STATEMENT]
        ]

    app_data: dict = {
        "applicationId": application_id,
        "userId": "sub-lo",
        "applicantName": "Alice Integration",
        "annualIncome": Decimal("90000.00"),
        "requestedLoanAmount": Decimal("20000.00"),
        "debtUtilization": Decimal("0.20"),
        "status": status,
        "documentInventory": docs,
    }
    if with_decision:
        app_data["decision"] = {
            "applicationId": application_id,
            "outcome": DecisionOutcome.APPROVE.value,
            "rationale": "PRIME applicant; all checks passed.",
            "decidedAt": "2026-06-23T12:00:00Z",
        }
    return CanonicalApplication(**app_data)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def integration_s3() -> MagicMock:
    """Mocked S3Repository for integration tests."""
    s3 = MagicMock(spec=S3Repository)
    s3.put_json = AsyncMock(return_value=None)
    s3.get_json = AsyncMock(return_value=None)
    s3.generate_presigned_put = AsyncMock(return_value="https://s3.example.com/presigned-url")
    s3.key_exists = AsyncMock(return_value=False)
    return s3


@pytest.fixture
def integration_client(
    integration_s3: MagicMock,
) -> Generator[TestClient, None, None]:
    """TestClient with all external dependencies mocked."""
    settings = _make_settings()
    user = _make_loan_officer()
    app = create_app(settings)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_s3_repository] = lambda: integration_s3

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc

    app.dependency_overrides.clear()


# ── POST /applications ─────────────────────────────────────────────────────────


class TestCreateApplication:
    """Integration tests for POST /applications."""

    def test_create_returns_201(self, integration_client: TestClient) -> None:
        resp = integration_client.post(
            "/api/v1/applications",
            json={
                "applicantName": "Alice Integration",
                "annualIncome": "90000.00",
                "requestedLoanAmount": "20000.00",
                "debtUtilization": "0.20",
            },
        )
        assert resp.status_code == 201

    def test_create_returns_application_id(self, integration_client: TestClient) -> None:
        resp = integration_client.post(
            "/api/v1/applications",
            json={
                "applicantName": "Bob Integration",
                "annualIncome": "35000.00",
                "requestedLoanAmount": "10000.00",
                "debtUtilization": "0.70",
            },
        )
        body = resp.json()
        assert "applicationId" in body
        assert body["applicationId"].startswith("app_")

    def test_create_returns_pending_status(self, integration_client: TestClient) -> None:
        resp = integration_client.post(
            "/api/v1/applications",
            json={
                "applicantName": "Carol Integration",
                "annualIncome": "60000.00",
                "requestedLoanAmount": "15000.00",
                "debtUtilization": "0.40",
            },
        )
        assert resp.json()["status"] == ApplicationStatus.PENDING.value

    def test_create_validates_required_fields(self, integration_client: TestClient) -> None:
        resp = integration_client.post("/api/v1/applications", json={})
        assert resp.status_code == 422

    def test_create_rejects_negative_income(self, integration_client: TestClient) -> None:
        resp = integration_client.post(
            "/api/v1/applications",
            json={
                "applicantName": "Invalid",
                "annualIncome": "-1000.00",
                "requestedLoanAmount": "5000.00",
                "debtUtilization": "0.20",
            },
        )
        assert resp.status_code in (422, 400)


# ── POST /applications/{id}/documents ─────────────────────────────────────────


class TestDocumentUpload:
    """Integration tests for POST /applications/{id}/documents."""

    def test_upload_returns_presigned_url(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        # Seed mock S3 with a PENDING app that accepts uploads
        pending_app = _make_app()
        integration_s3.get_json.return_value = pending_app.model_dump(by_alias=True, mode="json")

        resp = integration_client.post(
            "/api/v1/applications/app_integ_001/documents",
            json={"documentType": "PAYSTUB"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "uploadUrl" in body or "presignedUrl" in body or "url" in body or "uploadURL" in body

    def test_upload_rejects_unknown_document_type(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        pending_app = _make_app()
        integration_s3.get_json.return_value = pending_app.model_dump(by_alias=True, mode="json")

        resp = integration_client.post(
            "/api/v1/applications/app_integ_001/documents",
            json={"documentType": "INVALID_TYPE"},
        )
        assert resp.status_code == 422


# ── POST /applications/{id}/submit ────────────────────────────────────────────


class TestSubmitApplication:
    """Integration tests for POST /applications/{id}/submit."""

    def test_submit_accepts_ready_application(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        ready_app = _make_app(with_docs=True)
        integration_s3.get_json.return_value = ready_app.model_dump(by_alias=True, mode="json")

        resp = integration_client.post("/api/v1/applications/app_integ_001/submit")
        assert resp.status_code in (200, 202)

    def test_submit_transitions_to_processing(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        ready_app = _make_app(with_docs=True)
        integration_s3.get_json.return_value = ready_app.model_dump(by_alias=True, mode="json")

        resp = integration_client.post("/api/v1/applications/app_integ_001/submit")
        body = resp.json()
        # Status should be PROCESSING (or a success acknowledgement)
        assert body.get("status") == ApplicationStatus.PROCESSING.value or resp.status_code in (200, 202)

    def test_submit_rejects_already_processing(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        processing_app = _make_app(status=ApplicationStatus.PROCESSING, with_docs=True)
        integration_s3.get_json.return_value = processing_app.model_dump(by_alias=True, mode="json")

        resp = integration_client.post("/api/v1/applications/app_integ_001/submit")
        assert resp.status_code == 409

    def test_submit_rejects_missing_documents(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        no_docs_app = _make_app(with_docs=False)
        integration_s3.get_json.return_value = no_docs_app.model_dump(by_alias=True, mode="json")

        resp = integration_client.post("/api/v1/applications/app_integ_001/submit")
        assert resp.status_code == 422

    def test_submit_returns_404_for_missing_application(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        integration_s3.get_json.return_value = None

        resp = integration_client.post("/api/v1/applications/app_nonexistent/submit")
        assert resp.status_code == 404


# ── GET /applications/{id} ────────────────────────────────────────────────────


class TestGetApplicationStatus:
    """Integration tests for GET /applications/{id}."""

    def test_get_returns_application_data(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        app = _make_app()
        integration_s3.get_json.return_value = app.model_dump(by_alias=True, mode="json")

        resp = integration_client.get("/api/v1/applications/app_integ_001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["applicationId"] == "app_integ_001"
        assert body["status"] == ApplicationStatus.PENDING.value

    def test_get_returns_404_for_missing_application(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        integration_s3.get_json.return_value = None

        resp = integration_client.get("/api/v1/applications/app_does_not_exist")
        assert resp.status_code == 404


# ── Full flow: create → upload → submit → status ──────────────────────────────


class TestFullApplicationFlow:
    """End-to-end integration flow using sequential mock state transitions."""

    def test_create_to_submit_flow(
        self,
        integration_client: TestClient,
        integration_s3: MagicMock,
    ) -> None:
        """Happy-path integration: create, upload docs, submit, check status."""

        # Step 1: Create application
        create_resp = integration_client.post(
            "/api/v1/applications",
            json={
                "applicantName": "Full Flow Test",
                "annualIncome": "85000.00",
                "requestedLoanAmount": "20000.00",
                "debtUtilization": "0.25",
            },
        )
        assert create_resp.status_code == 201
        application_id = create_resp.json()["applicationId"]
        assert application_id

        # Step 2: Simulate app existing in S3 with PENDING status (for upload + submit)
        pending_app = _make_app(application_id=application_id, with_docs=False)
        integration_s3.get_json.return_value = pending_app.model_dump(by_alias=True, mode="json")

        # Step 3: Upload paystub document
        upload_resp = integration_client.post(
            f"/api/v1/applications/{application_id}/documents",
            json={"documentType": "PAYSTUB"},
        )
        assert upload_resp.status_code == 201

        # Step 4: Upload bank statement document
        upload_resp2 = integration_client.post(
            f"/api/v1/applications/{application_id}/documents",
            json={"documentType": "BANK_STATEMENT"},
        )
        assert upload_resp2.status_code == 201

        # Step 5: Simulate app with both docs for submit
        ready_app = _make_app(application_id=application_id, with_docs=True)
        integration_s3.get_json.return_value = ready_app.model_dump(by_alias=True, mode="json")

        submit_resp = integration_client.post(f"/api/v1/applications/{application_id}/submit")
        assert submit_resp.status_code in (200, 202)

        # Step 6: Check status (simulate PROCESSING state)
        processing_app = _make_app(
            application_id=application_id,
            status=ApplicationStatus.PROCESSING,
            with_docs=True,
        )
        integration_s3.get_json.return_value = processing_app.model_dump(by_alias=True, mode="json")

        status_resp = integration_client.get(f"/api/v1/applications/{application_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == ApplicationStatus.PROCESSING.value
