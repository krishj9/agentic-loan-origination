"""Tests for DriftDetector (P6-T7)."""

from decimal import Decimal
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import pytest
from shared.schemas import DecisionOutcome, RiskProfile

from evaluation.replay.drift import DriftDetector, DriftReport
from evaluation.replay.runner import RunResult
from evaluation.replay.trace import ExecutionStatus, ExecutionTrace, StateSnapshot
from evaluation.scenarios import ScenarioGenerator


# ── Policy YAML path ──────────────────────────────────────────────────────────

_POLICY_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "tools" / "config" / "risk_policy.yaml"
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_result(
    scenario_id: str = "test",
    annual_income: str = "90000.00",
    debt_utilization: str = "0.20",
    observed_profile: str = "PRIME",
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
) -> RunResult:
    generator = ScenarioGenerator(base_seed=42)
    scenario = generator.generate_end_to_end_scenario(
        scenario_id=scenario_id,
        risk_profile=RiskProfile.PRIME,
        expected_outcome=DecisionOutcome.APPROVE,
        seed=100,
    )
    # Patch financials into the canonical application
    app = scenario.canonical_application
    object.__setattr__(app, "annual_income", Decimal(annual_income))
    object.__setattr__(app, "debt_utilization", Decimal(debt_utilization))

    fields = {
        "risk_response": {"riskProfile": observed_profile},
        "decision": {"outcome": "APPROVE"},
    }

    trace = ExecutionTrace(
        trace_id=f"trace_{scenario_id}",
        scenario_id=scenario_id,
        started_at=datetime.utcnow(),
        status=status,
        final_state=StateSnapshot(application_id=scenario_id, fields=fields),
    )

    return RunResult(
        scenario_id=scenario_id,
        scenario=scenario,
        trace=trace,
        validation_passed=True,
        validation_errors=[],
        duration_ms=100.0,
    )


# ── DriftDetector tests ────────────────────────────────────────────────────────


@pytest.mark.skipif(not _POLICY_PATH.exists(), reason="risk_policy.yaml not found")
class TestDriftDetector:
    """Tests for DriftDetector against the actual risk_policy.yaml."""

    @pytest.fixture
    def detector(self) -> DriftDetector:
        return DriftDetector(policy_path=_POLICY_PATH)

    # ── _classify tests ───────────────────────────────────────────────────────

    def test_classify_prime_high_income_low_util(self, detector: DriftDetector) -> None:
        profile = detector._classify(Decimal("90000"), Decimal("0.20"))
        assert profile == "PRIME"

    def test_classify_prime_boundary_above_threshold(self, detector: DriftDetector) -> None:
        """income > 80000 AND util < 0.30 → PRIME"""
        profile = detector._classify(Decimal("80001"), Decimal("0.29"))
        assert profile == "PRIME"

    def test_classify_subprime_low_income(self, detector: DriftDetector) -> None:
        """income < 40000 → SUBPRIME"""
        profile = detector._classify(Decimal("35000"), Decimal("0.40"))
        assert profile == "SUBPRIME"

    def test_classify_subprime_high_utilization(self, detector: DriftDetector) -> None:
        """util > 0.60 → SUBPRIME"""
        profile = detector._classify(Decimal("70000"), Decimal("0.65"))
        assert profile == "SUBPRIME"

    def test_classify_near_prime_middle_values(self, detector: DriftDetector) -> None:
        """40000 < income < 80000 AND util between 0.30 and 0.60 → NEAR_PRIME"""
        profile = detector._classify(Decimal("60000"), Decimal("0.45"))
        assert profile == "NEAR_PRIME"

    def test_classify_near_prime_not_prime_not_subprime(self, detector: DriftDetector) -> None:
        """income at 80000 boundary (not strictly > 80000) → falls through to NEAR_PRIME"""
        profile = detector._classify(Decimal("80000"), Decimal("0.25"))
        # 80000 is NOT strictly > 80000 → not PRIME
        assert profile == "NEAR_PRIME"

    # ── annotate tests ────────────────────────────────────────────────────────

    def test_annotate_no_drift_when_profiles_match(self, detector: DriftDetector) -> None:
        result = _make_result(
            scenario_id="no_drift",
            annual_income="90000",
            debt_utilization="0.20",
            observed_profile="PRIME",
        )
        detector.annotate([result])
        assert result.drift_detected is False

    def test_annotate_drift_when_profile_mismatch(self, detector: DriftDetector) -> None:
        """Engine returns SUBPRIME but policy says PRIME → drift."""
        result = _make_result(
            scenario_id="drift_mismatch",
            annual_income="90000",
            debt_utilization="0.20",
            observed_profile="SUBPRIME",  # wrong!
        )
        detector.annotate([result])
        assert result.drift_detected is True

    def test_annotate_skips_failed_execution(self, detector: DriftDetector) -> None:
        result = _make_result(
            scenario_id="failed_exec",
            annual_income="90000",
            debt_utilization="0.20",
            observed_profile="PRIME",
            status=ExecutionStatus.FAILED,
        )
        # Remove final_state to simulate failed trace
        object.__setattr__(result.trace, "final_state", None)
        detector.annotate([result])
        assert result.drift_detected is False

    def test_annotate_multiple_results(self, detector: DriftDetector) -> None:
        results = [
            _make_result("clean_prime", "90000", "0.20", "PRIME"),
            _make_result("clean_subprime", "35000", "0.40", "SUBPRIME"),
            _make_result("drifted", "90000", "0.20", "NEAR_PRIME"),  # should be PRIME
        ]
        detector.annotate(results)
        assert results[0].drift_detected is False
        assert results[1].drift_detected is False
        assert results[2].drift_detected is True

    # ── build_report tests ────────────────────────────────────────────────────

    def test_build_report_no_drift(self, detector: DriftDetector) -> None:
        results = [
            _make_result(f"clean_{i}", "90000", "0.20", "PRIME")
            for i in range(3)
        ]
        detector.annotate(results)
        report = detector.build_report(results)
        assert isinstance(report, DriftReport)
        assert report.drift_count == 0
        assert report.clean_count == 3
        assert report.drift_rate_pct == 0.0

    def test_build_report_with_drift(self, detector: DriftDetector) -> None:
        results = [
            _make_result("clean", "90000", "0.20", "PRIME"),
            _make_result("drifted", "90000", "0.20", "SUBPRIME"),  # wrong band
        ]
        detector.annotate(results)
        report = detector.build_report(results)
        assert report.drift_count == 1
        assert report.clean_count == 1
        assert report.drift_rate_pct == 50.0
        assert len(report.events) == 1
        assert report.events[0].scenario_id == "drifted"
        assert report.events[0].expected_profile == "PRIME"
        assert report.events[0].observed_profile == "SUBPRIME"

    def test_drift_event_contains_meaningful_reason(self, detector: DriftDetector) -> None:
        results = [
            _make_result("drifted", "90000", "0.20", "NEAR_PRIME"),
        ]
        detector.annotate(results)
        report = detector.build_report(results)
        assert len(report.events) == 1
        assert "PRIME" in report.events[0].reason
        assert "NEAR_PRIME" in report.events[0].reason


class TestDriftDetectorMissingPolicy:
    """Test DriftDetector with a missing policy file."""

    def test_raises_file_not_found_for_missing_policy(self) -> None:
        with pytest.raises(FileNotFoundError):
            DriftDetector(policy_path=Path("/nonexistent/risk_policy.yaml"))
