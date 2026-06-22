"""Canonical Pydantic v2 schemas.

Import directly from sub-modules for clarity, or use the convenience
re-exports below for the most commonly used types.
"""

from shared.schemas.application import CanonicalApplication, Document
from shared.schemas.audit import AuditContext
from shared.schemas.compliance import ComplianceFlag, ComplianceResult
from shared.schemas.decision import Decision
from shared.schemas.documents import BankStatementFields, PayStubFields, Transaction
from shared.schemas.enums import (
    AccountType,
    ApplicationStatus,
    ComplianceAction,
    ComplianceSeverity,
    DecisionOutcome,
    DocumentType,
    RiskFlag,
    RiskProfile,
)
from shared.schemas.risk import RiskRequest, RiskResponse, Tradeline

__all__ = [
    # enums
    "AccountType",
    "ApplicationStatus",
    "ComplianceAction",
    "ComplianceSeverity",
    "DecisionOutcome",
    "DocumentType",
    "RiskFlag",
    "RiskProfile",
    # audit
    "AuditContext",
    # documents
    "Transaction",
    "PayStubFields",
    "BankStatementFields",
    # application
    "Document",
    "CanonicalApplication",
    # risk
    "Tradeline",
    "RiskRequest",
    "RiskResponse",
    # compliance
    "ComplianceFlag",
    "ComplianceResult",
    # decision
    "Decision",
]
