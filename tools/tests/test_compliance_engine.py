"""Tests for the compliance engine — P4-T5/T9.

Acceptance criteria (P4-T9):
  * Rule matrix covered: all four rules tested triggered and not-triggered.
  * Action derivation: DECLINE for CRITICAL/HIGH, REFER for MEDIUM, APPROVE for clean.
  * Determinism: same inputs → identical result.
  * All flags present in output (both pass and fail) for complete audit trace.
  * Descriptions populated for triggered rules.
"""

import pytest
from decimal import Decimal

from shared.schemas import ComplianceAction, ComplianceSeverity, RiskProfile
from tools.compliance_engine import evaluate


# ── Helper builders ──────────────────────────────────────────────────────────

def _eval(
    *,
    application_id: str = "app-cmp-001",
    annual_income: Decimal = Decimal("85000"),
    requested_loan_amount: Decimal = Decimal("20000"),
    risk_profile: RiskProfile = RiskProfile.PRIME,
    document_types_present: list[str] | None = None,
    applicant_name: str | None = None,
):
    docs = document_types_present if document_types_present is not None else ["PAYSTUB", "BANK_STATEMENT"]
    return evaluate(
        application_id=application_id,
        annual_income=annual_income,
        requested_loan_amount=requested_loan_amount,
        risk_profile=risk_profile,
        document_types_present=docs,
        applicant_name=applicant_name,
    )


# ── Happy-path: all rules pass ───────────────────────────────────────────────

class TestHappyPath:
    def test_all_rules_pass_returns_approve(self) -> None:
        result = _eval()
        assert result.recommended_action == ComplianceAction.APPROVE
        assert result.passed is True
        assert len(result.flags) == 4  # all 4 rules evaluated

    def test_no_triggered_flags_when_clean(self) -> None:
        result = _eval()
        triggered = [f for f in result.flags if f.triggered]
        assert triggered == []

    def test_application_id_echoed(self) -> None:
        result = _eval(application_id="app-echo-test")
        assert result.application_id == "app-echo-test"


# ── MISSING_CRITICAL_FIELDS ──────────────────────────────────────────────────

class TestMissingCriticalFields:
    def test_zero_income_triggers_critical(self) -> None:
        result = _eval(annual_income=Decimal("0"))
        flag = next(f for f in result.flags if f.rule_id == "MISSING_CRITICAL_FIELDS")
        assert flag.triggered is True
        assert flag.severity == ComplianceSeverity.CRITICAL
        assert result.recommended_action == ComplianceAction.DECLINE
        assert result.passed is False

    def test_zero_loan_amount_triggers_critical(self) -> None:
        result = _eval(requested_loan_amount=Decimal("0"))
        flag = next(f for f in result.flags if f.rule_id == "MISSING_CRITICAL_FIELDS")
        assert flag.triggered is True

    def test_negative_income_triggers_critical(self) -> None:
        result = _eval(annual_income=Decimal("-5000"))
        flag = next(f for f in result.flags if f.rule_id == "MISSING_CRITICAL_FIELDS")
        assert flag.triggered is True

    def test_positive_values_do_not_trigger(self) -> None:
        result = _eval(annual_income=Decimal("50000"), requested_loan_amount=Decimal("10000"))
        flag = next(f for f in result.flags if f.rule_id == "MISSING_CRITICAL_FIELDS")
        assert flag.triggered is False


# ── REQUIRED_DOCUMENT_COMPLETENESS ──────────────────────────────────────────

class TestRequiredDocumentCompleteness:
    def test_missing_paystub_triggers_critical(self) -> None:
        result = _eval(document_types_present=["BANK_STATEMENT"])
        flag = next(f for f in result.flags if f.rule_id == "REQUIRED_DOCUMENT_COMPLETENESS")
        assert flag.triggered is True
        assert flag.severity == ComplianceSeverity.CRITICAL
        assert "PAYSTUB" in flag.description

    def test_missing_bank_statement_triggers_critical(self) -> None:
        result = _eval(document_types_present=["PAYSTUB"])
        flag = next(f for f in result.flags if f.rule_id == "REQUIRED_DOCUMENT_COMPLETENESS")
        assert flag.triggered is True
        assert "BANK_STATEMENT" in flag.description

    def test_missing_both_triggers_critical(self) -> None:
        result = _eval(document_types_present=[])
        flag = next(f for f in result.flags if f.rule_id == "REQUIRED_DOCUMENT_COMPLETENESS")
        assert flag.triggered is True

    def test_all_present_does_not_trigger(self) -> None:
        result = _eval(document_types_present=["PAYSTUB", "BANK_STATEMENT"])
        flag = next(f for f in result.flags if f.rule_id == "REQUIRED_DOCUMENT_COMPLETENESS")
        assert flag.triggered is False
        assert "present" in flag.description.lower()


# ── LOAN_TO_INCOME_RATIO ─────────────────────────────────────────────────────

class TestLoanToIncomeRatio:
    def test_exceeds_40pct_triggers_high(self) -> None:
        # 40,001 / 85,000 = ~47% > 40%
        result = _eval(annual_income=Decimal("85000"), requested_loan_amount=Decimal("40001"))
        flag = next(f for f in result.flags if f.rule_id == "LOAN_TO_INCOME_RATIO")
        assert flag.triggered is True
        assert flag.severity == ComplianceSeverity.HIGH

    def test_exactly_40pct_does_not_trigger(self) -> None:
        # 34,000 / 85,000 = 40.0% — exactly at limit
        result = _eval(annual_income=Decimal("85000"), requested_loan_amount=Decimal("34000"))
        flag = next(f for f in result.flags if f.rule_id == "LOAN_TO_INCOME_RATIO")
        assert flag.triggered is False

    def test_below_40pct_does_not_trigger(self) -> None:
        result = _eval(annual_income=Decimal("100000"), requested_loan_amount=Decimal("30000"))
        flag = next(f for f in result.flags if f.rule_id == "LOAN_TO_INCOME_RATIO")
        assert flag.triggered is False

    def test_description_contains_values(self) -> None:
        result = _eval(annual_income=Decimal("50000"), requested_loan_amount=Decimal("30000"))
        flag = next(f for f in result.flags if f.rule_id == "LOAN_TO_INCOME_RATIO")
        assert "50,000" in flag.description or "50000" in flag.description


# ── RISK_BAND_LOAN_CEILING ───────────────────────────────────────────────────

class TestRiskBandLoanCeiling:
    def test_prime_below_100k_passes(self) -> None:
        result = _eval(risk_profile=RiskProfile.PRIME, requested_loan_amount=Decimal("99000"))
        flag = next(f for f in result.flags if f.rule_id == "RISK_BAND_LOAN_CEILING")
        assert flag.triggered is False

    def test_prime_above_100k_triggers(self) -> None:
        result = _eval(
            risk_profile=RiskProfile.PRIME,
            requested_loan_amount=Decimal("100001"),
            annual_income=Decimal("500000"),
        )
        flag = next(f for f in result.flags if f.rule_id == "RISK_BAND_LOAN_CEILING")
        assert flag.triggered is True

    def test_near_prime_above_50k_triggers(self) -> None:
        result = _eval(
            risk_profile=RiskProfile.NEAR_PRIME,
            requested_loan_amount=Decimal("55000"),
            annual_income=Decimal("200000"),
        )
        flag = next(f for f in result.flags if f.rule_id == "RISK_BAND_LOAN_CEILING")
        assert flag.triggered is True

    def test_subprime_above_20k_triggers(self) -> None:
        result = _eval(
            risk_profile=RiskProfile.SUBPRIME,
            requested_loan_amount=Decimal("25000"),
            annual_income=Decimal("200000"),
        )
        flag = next(f for f in result.flags if f.rule_id == "RISK_BAND_LOAN_CEILING")
        assert flag.triggered is True

    def test_subprime_below_20k_passes(self) -> None:
        result = _eval(
            risk_profile=RiskProfile.SUBPRIME,
            requested_loan_amount=Decimal("15000"),
            annual_income=Decimal("38000"),
        )
        flag = next(f for f in result.flags if f.rule_id == "RISK_BAND_LOAN_CEILING")
        assert flag.triggered is False


# ── Action derivation ────────────────────────────────────────────────────────

class TestActionDerivation:
    def test_critical_flag_produces_decline(self) -> None:
        result = _eval(document_types_present=[])  # missing docs = CRITICAL
        assert result.recommended_action == ComplianceAction.DECLINE

    def test_high_flag_produces_decline(self) -> None:
        result = _eval(
            risk_profile=RiskProfile.SUBPRIME,
            requested_loan_amount=Decimal("50000"),
            annual_income=Decimal("200000"),
        )
        assert result.recommended_action == ComplianceAction.DECLINE

    def test_clean_produces_approve(self) -> None:
        result = _eval()
        assert result.recommended_action == ComplianceAction.APPROVE

    def test_passed_false_when_declined(self) -> None:
        result = _eval(annual_income=Decimal("0"))
        assert result.passed is False

    def test_passed_true_when_approved(self) -> None:
        result = _eval()
        assert result.passed is True


# ── Determinism ──────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_inputs_produce_identical_result(self) -> None:
        kwargs = dict(
            annual_income=Decimal("65000"),
            requested_loan_amount=Decimal("20000"),
            risk_profile=RiskProfile.NEAR_PRIME,
            document_types_present=["PAYSTUB", "BANK_STATEMENT"],
        )
        r1 = _eval(**kwargs)  # type: ignore[arg-type]
        r2 = _eval(**kwargs)  # type: ignore[arg-type]
        assert r1.recommended_action == r2.recommended_action
        assert r1.passed == r2.passed
        assert len(r1.flags) == len(r2.flags)
        for f1, f2 in zip(r1.flags, r2.flags):
            assert f1.rule_id == f2.rule_id
            assert f1.triggered == f2.triggered
            assert f1.severity == f2.severity


# ── All four rules always evaluated ──────────────────────────────────────────

class TestCompleteAuditTrace:
    def test_always_four_flags(self) -> None:
        result = _eval()
        assert len(result.flags) == 4

    def test_rule_ids_are_canonical(self) -> None:
        result = _eval()
        rule_ids = {f.rule_id for f in result.flags}
        assert rule_ids == {
            "MISSING_CRITICAL_FIELDS",
            "REQUIRED_DOCUMENT_COMPLETENESS",
            "LOAN_TO_INCOME_RATIO",
            "RISK_BAND_LOAN_CEILING",
        }

    def test_flag_descriptions_non_empty(self) -> None:
        result = _eval()
        for flag in result.flags:
            assert len(flag.description) > 5
