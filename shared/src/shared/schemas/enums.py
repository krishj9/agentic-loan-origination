"""Canonical enumerations used across the loan origination system.

All enumerations are string-based so they serialize cleanly to/from JSON
and remain readable in S3 artifacts and CloudWatch logs.
"""

from enum import StrEnum


class RiskProfile(StrEnum):
    """Risk classification bands produced by the mock risk engine."""

    PRIME = "PRIME"
    NEAR_PRIME = "NEAR_PRIME"
    SUBPRIME = "SUBPRIME"


class DocumentType(StrEnum):
    """Supported document types for upload and LlamaParse processing."""

    PAYSTUB = "PAYSTUB"
    BANK_STATEMENT = "BANK_STATEMENT"
    ID = "ID"
    OTHER = "OTHER"


class DecisionOutcome(StrEnum):
    """Final underwriting decision outcome."""

    APPROVE = "APPROVE"
    REFER = "REFER"
    DECLINE = "DECLINE"


class ApplicationStatus(StrEnum):
    """Lifecycle state of a loan application."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class AccountType(StrEnum):
    """Tradeline account types used in synthetic tradeline generation."""

    CREDIT_CARD = "CREDIT_CARD"
    AUTO_LOAN = "AUTO_LOAN"
    MORTGAGE = "MORTGAGE"


class RiskFlag(StrEnum):
    """Flags that can be raised by the mock risk engine for explainability."""

    HIGH_UTILIZATION = "HIGH_UTILIZATION"
    LOW_INCOME = "LOW_INCOME"
    NEAR_PRIME_INCOME = "NEAR_PRIME_INCOME"
    MODERATE_UTILIZATION = "MODERATE_UTILIZATION"


class ComplianceSeverity(StrEnum):
    """Severity levels for compliance flags."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceAction(StrEnum):
    """Recommended action produced by the compliance engine."""

    APPROVE = "APPROVE"
    REFER = "REFER"
    DECLINE = "DECLINE"
