"""Compliance engine package — ``tools.compliance_engine.evaluate`` (P4-T5).

Public interface::

    from tools.compliance_engine import evaluate
    result = evaluate(
        application_id="app_001",
        annual_income=Decimal("85000"),
        requested_loan_amount=Decimal("20000"),
        risk_profile=RiskProfile.PRIME,
        document_types_present=["PAYSTUB", "BANK_STATEMENT"],
    )
"""

from tools.compliance_engine.engine import evaluate

__all__ = ["evaluate"]
