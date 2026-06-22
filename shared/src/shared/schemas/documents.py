"""Normalized field schemas for LlamaParse-extracted financial documents.

The normalization layer (agents/tools/normalize.py, Phase 4) maps raw parser
output onto these models, isolating the rest of the system from parser-specific
output differences as described in design §6.3.

Only two document types are supported in v1:
  - Pay stubs  (PayStubFields)
  - Bank statements  (BankStatementFields)
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    """A single transaction row from a bank statement."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_date: date = Field(alias="date", description="Transaction date.")
    description: str = Field(description="Merchant / narration text.")
    amount: Decimal = Field(description="Transaction amount. Negative = debit, positive = credit.")
    running_balance: Decimal | None = Field(
        default=None,
        alias="balance",
        description="Running balance after this transaction, when present in the statement.",
    )


class PayStubFields(BaseModel):
    """Canonical fields extracted from a pay stub PDF.

    All monetary values are Decimal to avoid floating-point rounding in
    downstream financial calculations.

    Required fields align with requirements §6.1:
      employee_name, employer_name, pay_period_start, pay_period_end,
      pay_date, gross_pay, deductions, net_pay.
    YTD values are optional but recommended.
    """

    model_config = ConfigDict(populate_by_name=True)

    employee_name: str = Field(description="Full name of the employee as printed on the stub.")
    employer_name: str = Field(description="Name of the employer / company.")
    pay_period_start: date = Field(description="First day of the pay period.")
    pay_period_end: date = Field(description="Last day of the pay period.")
    pay_date: date = Field(description="Date the payment was issued.")
    gross_pay: Decimal = Field(description="Total gross earnings for the pay period.")
    deductions: Decimal = Field(description="Total deductions (taxes + other) for the period.")
    net_pay: Decimal = Field(description="Take-home pay after deductions.")
    ytd_gross_pay: Decimal | None = Field(default=None, description="Year-to-date gross pay.")
    ytd_net_pay: Decimal | None = Field(default=None, description="Year-to-date net pay.")

    # Extraction confidence — populated by the normalization layer
    confidence_notes: list[str] = Field(
        default_factory=list,
        description="Parser confidence notes or warnings for this document.",
    )


class BankStatementFields(BaseModel):
    """Canonical fields extracted from a bank statement PDF.

    Required fields align with requirements §6.1:
      account_holder_name, statement_period_start, statement_period_end,
      account_number_masked, opening_balance, closing_balance, transactions.
    """

    model_config = ConfigDict(populate_by_name=True)

    account_holder_name: str = Field(description="Name of the account holder as printed on the statement.")
    statement_period_start: date = Field(description="First day of the statement period.")
    statement_period_end: date = Field(description="Last day of the statement period.")
    account_number_masked: str = Field(
        description="Masked account number (e.g. '****1234'). Never a full account number.",
    )
    opening_balance: Decimal = Field(description="Balance at the start of the statement period.")
    closing_balance: Decimal = Field(description="Balance at the end of the statement period.")
    transactions: list[Transaction] = Field(
        default_factory=list,
        description="Individual transaction rows from the statement body.",
    )

    # Extraction confidence — populated by the normalization layer
    confidence_notes: list[str] = Field(
        default_factory=list,
        description="Parser confidence notes or warnings for this document.",
    )
