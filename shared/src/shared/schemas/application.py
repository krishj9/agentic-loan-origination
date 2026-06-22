"""Top-level application schema and document inventory models.

CanonicalApplication is the single source of truth that flows through the
LangGraph supervisor state (design §5.2).  It is populated incrementally:
  - At submission: applicant metadata + document inventory.
  - After parsing:  pay_stub_data and bank_statement_data.
  - After risk:     populated via RiskResponse in the graph state.
  - After decision: status transitions to COMPLETED or MANUAL_REVIEW.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas.audit import AuditContext
from shared.schemas.documents import BankStatementFields, PayStubFields
from shared.schemas.enums import ApplicationStatus, DocumentType


class Document(BaseModel):
    """A single uploaded document in an application's inventory."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(description="Unique document identifier (UUID).")
    application_id: str = Field(description="Parent application identifier.")
    document_type: DocumentType = Field(description="Classifies the uploaded file.")
    s3_key: str = Field(
        description="Full S3 object key under the 'incoming/{application_id}/' prefix.",
    )
    uploaded_at: datetime = Field(description="UTC timestamp when the presigned upload was completed.")
    parse_status: str = Field(
        default="PENDING",
        description="Parse lifecycle: PENDING | PROCESSING | COMPLETED | FAILED.",
    )


class CanonicalApplication(BaseModel):
    """Canonical application record — the shared LangGraph state payload.

    Financial inputs used by the risk engine:
      annual_income:      annualised income derived from pay stub gross_pay.
      debt_utilization:   overall utilisation ratio (0.0 – 1.0) supplied at
                          submission or derived from bank statement data.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "applicationId": "app_01J000000000000000000000",
                "userId": "cognito-sub-abc123",
                "applicantName": "Jane Smith",
                "annualIncome": "85000.00",
                "requestedLoanAmount": "20000.00",
                "debtUtilization": "0.25",
                "status": "PENDING",
            }
        },
    )

    application_id: str = Field(alias="applicationId", description="Unique application identifier.")
    user_id: str = Field(alias="userId", description="Cognito sub of the submitting loan officer.")
    applicant_name: str = Field(alias="applicantName", description="Full name of the loan applicant.")
    annual_income: Decimal = Field(
        alias="annualIncome",
        description="Annualised gross income (USD). Derived from pay stub or supplied at submission.",
    )
    requested_loan_amount: Decimal = Field(
        alias="requestedLoanAmount",
        description="Loan amount requested by the applicant (USD).",
    )
    debt_utilization: Decimal = Field(
        alias="debtUtilization",
        description=(
            "Aggregate debt utilisation ratio (0.0 – 1.0). " "0.25 means 25 % of available revolving credit is in use."
        ),
    )
    status: ApplicationStatus = Field(
        default=ApplicationStatus.PENDING,
        description="Current lifecycle status of the application.",
    )

    # Document inventory — populated as files are uploaded
    document_inventory: list[Document] = Field(
        default_factory=list,
        alias="documentInventory",
        description="Uploaded documents associated with this application.",
    )

    # Extracted / normalized financial data — populated by the extraction subgraph
    pay_stub_data: PayStubFields | None = Field(
        default=None,
        alias="payStubData",
        description="Normalized pay stub fields after LlamaParse extraction.",
    )
    bank_statement_data: BankStatementFields | None = Field(
        default=None,
        alias="bankStatementData",
        description="Normalized bank statement fields after LlamaParse extraction.",
    )

    # Audit envelope — attached before persisting to S3
    audit_context: AuditContext | None = Field(
        default=None,
        alias="auditContext",
        description="Audit metadata written into the S3 archive artifact.",
    )
