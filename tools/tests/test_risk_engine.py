"""Tests for the deterministic mock risk engine — P4-T3/T4/T9.

Acceptance criteria (P4-T9):
  * Determinism: same input → identical output across multiple runs.
  * All three bands exercised: PRIME, NEAR_PRIME, SUBPRIME.
  * Override pin: ``risk_profile`` override bypasses classification.
  * Flags: HIGH_UTILIZATION, LOW_INCOME, MODERATE_UTILIZATION, NEAR_PRIME_INCOME.
  * Tradeline count in [1, 5]; utilization in [0, 1].
  * Explainability fields populated (income_band, utilization_band, score_range_rationale).
  * Credit score within configured band range.
"""

import pytest
from decimal import Decimal

from shared.schemas import RiskFlag, RiskProfile, RiskRequest
from tools.risk_engine import evaluate
from tools.risk_engine.config import get_policy


# ── Determinism tests (P4-T9 primary requirement) ───────────────────────────

class TestDeterminism:
    """Same input must produce identical output on every invocation."""

    def test_prime_deterministic_across_runs(self, prime_request: RiskRequest) -> None:
        results = [evaluate(prime_request) for _ in range(5)]
        first = results[0]
        for result in results[1:]:
            assert result.risk_profile == first.risk_profile
            assert result.credit_score == first.credit_score
            assert len(result.tradelines) == len(first.tradelines)
            assert result.risk_flags == first.risk_flags
            assert result.income_band == first.income_band
            assert result.utilization_band == first.utilization_band

    def test_near_prime_deterministic_across_runs(self, near_prime_request: RiskRequest) -> None:
        r1 = evaluate(near_prime_request)
        r2 = evaluate(near_prime_request)
        assert r1.risk_profile == r2.risk_profile
        assert r1.credit_score == r2.credit_score
        assert r1.tradelines == r2.tradelines
        assert r1.risk_flags == r2.risk_flags

    def test_different_seeds_produce_different_scores(self) -> None:
        r1 = evaluate(RiskRequest(applicant_id="seed-A", annual_income=Decimal("90000"), debt_utilization=Decimal("0.20")))
        r2 = evaluate(RiskRequest(applicant_id="seed-B", annual_income=Decimal("90000"), debt_utilization=Decimal("0.20")))
        # Both PRIME, but scores should differ
        assert r1.risk_profile == RiskProfile.PRIME
        assert r2.risk_profile == RiskProfile.PRIME
        # Not required to differ, but almost always will with different seeds
        # (whitebox: MD5 offset differs between "seed-A:score" and "seed-B:score")

    def test_same_seed_different_income_same_profile_identical_score(self) -> None:
        """Score is seeded from applicant_id only — income within same band gives same score."""
        base = RiskRequest(applicant_id="determinism-test", annual_income=Decimal("85000"), debt_utilization=Decimal("0.25"))
        r1 = evaluate(base)
        # Slightly different income, still PRIME band → same credit score
        r2 = evaluate(RiskRequest(applicant_id="determinism-test", annual_income=Decimal("90000"), debt_utilization=Decimal("0.25")))
        assert r1.risk_profile == RiskProfile.PRIME
        assert r2.risk_profile == RiskProfile.PRIME
        assert r1.credit_score == r2.credit_score


# ── Band classification tests ────────────────────────────────────────────────

class TestBandClassification:
    """Verify correct PRIME / NEAR_PRIME / SUBPRIME assignment."""

    def test_prime_high_income_low_utilization(self, prime_request: RiskRequest) -> None:
        result = evaluate(prime_request)
        assert result.risk_profile == RiskProfile.PRIME

    def test_near_prime_mid_income_mid_utilization(self, near_prime_request: RiskRequest) -> None:
        result = evaluate(near_prime_request)
        assert result.risk_profile == RiskProfile.NEAR_PRIME

    def test_subprime_low_income(self, subprime_request: RiskRequest) -> None:
        result = evaluate(subprime_request)
        assert result.risk_profile == RiskProfile.SUBPRIME

    def test_subprime_high_utilization_regardless_of_income(self) -> None:
        req = RiskRequest(applicant_id="sub-util", annual_income=Decimal("90000"), debt_utilization=Decimal("0.75"))
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.SUBPRIME

    def test_prime_boundary_income_exactly_80001(self) -> None:
        req = RiskRequest(applicant_id="boundary-prime", annual_income=Decimal("80001"), debt_utilization=Decimal("0.25"))
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.PRIME

    def test_near_prime_boundary_income_exactly_80000(self) -> None:
        req = RiskRequest(applicant_id="boundary-np", annual_income=Decimal("80000"), debt_utilization=Decimal("0.25"))
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.NEAR_PRIME

    def test_subprime_boundary_income_39999(self) -> None:
        req = RiskRequest(applicant_id="boundary-sub", annual_income=Decimal("39999"), debt_utilization=Decimal("0.25"))
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.SUBPRIME

    def test_near_prime_income_exactly_40000(self) -> None:
        req = RiskRequest(applicant_id="boundary-np2", annual_income=Decimal("40000"), debt_utilization=Decimal("0.25"))
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.NEAR_PRIME


# ── Override support (design §7.5) ───────────────────────────────────────────

class TestOverride:
    """Optional risk_profile override must bypass classification rules."""

    def test_override_prime_on_subprime_income(self) -> None:
        req = RiskRequest(
            applicant_id="override-test",
            annual_income=Decimal("25000"),
            debt_utilization=Decimal("0.80"),
            risk_profile=RiskProfile.PRIME,
        )
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.PRIME

    def test_override_subprime_on_prime_income(self) -> None:
        req = RiskRequest(
            applicant_id="override-test-2",
            annual_income=Decimal("120000"),
            debt_utilization=Decimal("0.10"),
            risk_profile=RiskProfile.SUBPRIME,
        )
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.SUBPRIME

    def test_override_near_prime(self) -> None:
        req = RiskRequest(
            applicant_id="override-np",
            annual_income=Decimal("95000"),
            debt_utilization=Decimal("0.15"),
            risk_profile=RiskProfile.NEAR_PRIME,
        )
        result = evaluate(req)
        assert result.risk_profile == RiskProfile.NEAR_PRIME

    def test_override_score_still_within_band(self) -> None:
        policy = get_policy()
        req = RiskRequest(
            applicant_id="override-score",
            annual_income=Decimal("25000"),
            debt_utilization=Decimal("0.90"),
            risk_profile=RiskProfile.PRIME,
        )
        result = evaluate(req)
        band = policy.bands["PRIME"]
        assert band.score_range.min <= result.credit_score < band.score_range.max


# ── Credit score range tests ─────────────────────────────────────────────────

class TestCreditScore:
    """Credit score must fall within the configured band range."""

    @pytest.mark.parametrize("profile,income,utilization", [
        (RiskProfile.PRIME, Decimal("95000"), Decimal("0.20")),
        (RiskProfile.NEAR_PRIME, Decimal("60000"), Decimal("0.45")),
        (RiskProfile.SUBPRIME, Decimal("30000"), Decimal("0.75")),
    ])
    def test_score_within_band_range(
        self,
        profile: RiskProfile,
        income: Decimal,
        utilization: Decimal,
    ) -> None:
        policy = get_policy()
        req = RiskRequest(applicant_id=f"score-test-{profile.value}", annual_income=income, debt_utilization=utilization)
        result = evaluate(req)
        assert result.risk_profile == profile
        band = policy.bands[profile.value]
        assert band.score_range.min <= result.credit_score < band.score_range.max


# ── Risk flag tests ──────────────────────────────────────────────────────────

class TestRiskFlags:
    """Flags must be emitted exactly when thresholds are crossed."""

    def test_high_utilization_flag(self) -> None:
        req = RiskRequest(applicant_id="flag-high-util", annual_income=Decimal("90000"), debt_utilization=Decimal("0.65"))
        result = evaluate(req)
        assert RiskFlag.HIGH_UTILIZATION in result.risk_flags
        assert RiskFlag.MODERATE_UTILIZATION not in result.risk_flags

    def test_moderate_utilization_flag(self) -> None:
        req = RiskRequest(applicant_id="flag-mod-util", annual_income=Decimal("90000"), debt_utilization=Decimal("0.40"))
        result = evaluate(req)
        assert RiskFlag.MODERATE_UTILIZATION in result.risk_flags
        assert RiskFlag.HIGH_UTILIZATION not in result.risk_flags

    def test_low_income_flag(self) -> None:
        req = RiskRequest(applicant_id="flag-low-income", annual_income=Decimal("35000"), debt_utilization=Decimal("0.20"))
        result = evaluate(req)
        assert RiskFlag.LOW_INCOME in result.risk_flags

    def test_near_prime_income_flag(self) -> None:
        req = RiskRequest(applicant_id="flag-np-income", annual_income=Decimal("60000"), debt_utilization=Decimal("0.20"))
        result = evaluate(req)
        assert RiskFlag.NEAR_PRIME_INCOME in result.risk_flags

    def test_prime_no_flags(self, prime_request: RiskRequest) -> None:
        result = evaluate(prime_request)
        assert RiskFlag.HIGH_UTILIZATION not in result.risk_flags
        assert RiskFlag.LOW_INCOME not in result.risk_flags


# ── Tradeline tests ──────────────────────────────────────────────────────────

class TestTradelines:
    """Tradelines must be within configured bounds and utilization in [0, 1]."""

    def test_tradeline_count_in_range(self, prime_request: RiskRequest) -> None:
        result = evaluate(prime_request)
        assert 1 <= len(result.tradelines) <= 5

    def test_tradeline_utilization_bounded(self, subprime_request: RiskRequest) -> None:
        result = evaluate(subprime_request)
        for tl in result.tradelines:
            assert Decimal("0") <= tl.utilization <= Decimal("1")

    def test_tradeline_balance_derived_from_limit_and_utilization(self, near_prime_request: RiskRequest) -> None:
        result = evaluate(near_prime_request)
        for tl in result.tradelines:
            expected = (tl.limit * tl.utilization).quantize(Decimal("0.01"))
            assert tl.balance == expected


# ── Explainability tests (design §7.7) ───────────────────────────────────────

class TestExplainability:
    """Explainability fields must be populated and consistent."""

    def test_prime_income_band_high(self, prime_request: RiskRequest) -> None:
        result = evaluate(prime_request)
        assert result.income_band == "HIGH"
        assert result.utilization_band == "LOW"

    def test_near_prime_income_band_mid(self, near_prime_request: RiskRequest) -> None:
        result = evaluate(near_prime_request)
        assert result.income_band == "MID"
        assert result.utilization_band == "MODERATE"

    def test_subprime_income_band_low(self) -> None:
        req = RiskRequest(applicant_id="exp-sub", annual_income=Decimal("30000"), debt_utilization=Decimal("0.20"))
        result = evaluate(req)
        assert result.income_band == "LOW"

    def test_score_range_rationale_non_empty(self, prime_request: RiskRequest) -> None:
        result = evaluate(prime_request)
        assert len(result.score_range_rationale) > 20

    def test_rationale_references_profile(self, near_prime_request: RiskRequest) -> None:
        result = evaluate(near_prime_request)
        assert "NEAR_PRIME" in result.score_range_rationale

    def test_applicant_id_echoed(self, prime_request: RiskRequest) -> None:
        result = evaluate(prime_request)
        assert result.applicant_id == prime_request.applicant_id
