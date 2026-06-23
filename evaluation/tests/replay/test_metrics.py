"""Tests for MetricsCalculator (P6-T6)."""

from datetime import datetime

import pytest
from shared.schemas import DecisionOutcome, RiskProfile

from evaluation.replay.metrics import EvaluationMetrics, MetricsCalculator
from evaluation.replay.runner import RunResult
from evaluation.replay.trace import ExecutionStatus, ExecutionTrace, StateSnapshot
from evaluation.scenarios import ScenarioGenerator


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_trace(
    scenario_id: str = "test",
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
    outcome: str | None = "APPROVE",
    risk_profile: str = "PRIME",
) -> ExecutionTrace:
    fields: dict = {}
    if outcome is not None:
        fields["decision"] = {"outcome": outcome}
    if risk_profile:
        fields["risk_response"] = {"riskProfile": risk_profile}

    return ExecutionTrace(
        trace_id=f"trace_{scenario_id}",
        scenario_id=scenario_id,
        started_at=datetime.utcnow(),
        status=status,
        final_state=StateSnapshot(application_id=scenario_id, fields=fields) if fields else None,
    )


def _make_result(
    scenario_id: str = "test",
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
    outcome: str | None = "APPROVE",
    expected_outcome: str | None = "APPROVE",
    risk_profile: str = "PRIME",
    drift_detected: bool = False,
) -> RunResult:
    generator = ScenarioGenerator(base_seed=42)
    scenario = generator.generate_end_to_end_scenario(
        scenario_id=scenario_id,
        risk_profile=RiskProfile.PRIME,
        expected_outcome=DecisionOutcome.APPROVE,
        seed=100,
    )
    # Override the expected decision outcome to the requested value
    if expected_outcome is not None:
        object.__setattr__(scenario, "expected_decision_outcome", expected_outcome)
    else:
        object.__setattr__(scenario, "expected_decision_outcome", None)

    trace = _make_trace(scenario_id, status, outcome, risk_profile)

    return RunResult(
        scenario_id=scenario_id,
        scenario=scenario,
        trace=trace,
        validation_passed=True,
        validation_errors=[],
        duration_ms=100.0,
        drift_detected=drift_detected,
    )


# ── MetricsCalculator tests ────────────────────────────────────────────────────


class TestMetricsCalculator:
    """Tests for MetricsCalculator.calculate()."""

    @pytest.fixture
    def calculator(self) -> MetricsCalculator:
        return MetricsCalculator()

    def test_empty_results_returns_zero_metrics(self, calculator: MetricsCalculator) -> None:
        metrics = calculator.calculate([])
        assert metrics.total_scenarios == 0
        assert metrics.accuracy_pct == 0.0
        assert metrics.correct_count == 0
        assert metrics.false_positive_count == 0
        assert metrics.false_negative_count == 0
        assert metrics.drift_event_count == 0

    def test_all_correct_gives_100_accuracy(self, calculator: MetricsCalculator) -> None:
        results = [
            _make_result(f"s{i}", outcome="APPROVE", expected_outcome="APPROVE")
            for i in range(5)
        ]
        metrics = calculator.calculate(results)
        assert metrics.accuracy_pct == 100.0
        assert metrics.correct_count == 5
        assert metrics.false_positive_count == 0
        assert metrics.false_negative_count == 0

    def test_all_wrong_gives_0_accuracy(self, calculator: MetricsCalculator) -> None:
        results = [
            _make_result(f"s{i}", outcome="DECLINE", expected_outcome="APPROVE")
            for i in range(3)
        ]
        metrics = calculator.calculate(results)
        assert metrics.accuracy_pct == 0.0
        assert metrics.correct_count == 0

    def test_false_positive_counted_correctly(self, calculator: MetricsCalculator) -> None:
        """APPROVE when expected DECLINE/REFER → false positive."""
        results = [
            _make_result("fp1", outcome="APPROVE", expected_outcome="DECLINE"),
            _make_result("fp2", outcome="APPROVE", expected_outcome="REFER"),
        ]
        metrics = calculator.calculate(results)
        assert metrics.false_positive_count == 2
        assert metrics.false_negative_count == 0

    def test_false_negative_counted_correctly(self, calculator: MetricsCalculator) -> None:
        """DECLINE when expected APPROVE → false negative."""
        results = [
            _make_result("fn1", outcome="DECLINE", expected_outcome="APPROVE"),
        ]
        metrics = calculator.calculate(results)
        assert metrics.false_negative_count == 1
        assert metrics.false_positive_count == 0

    def test_drift_events_counted(self, calculator: MetricsCalculator) -> None:
        results = [
            _make_result("d1", drift_detected=True),
            _make_result("d2", drift_detected=False),
            _make_result("d3", drift_detected=True),
        ]
        metrics = calculator.calculate(results)
        assert metrics.drift_event_count == 2

    def test_scenarios_without_expected_outcome_excluded_from_accuracy(
        self, calculator: MetricsCalculator
    ) -> None:
        results = [
            _make_result("no_exp", outcome="APPROVE", expected_outcome=None),
            _make_result("with_exp", outcome="APPROVE", expected_outcome="APPROVE"),
        ]
        metrics = calculator.calculate(results)
        assert metrics.total_scenarios == 2
        assert metrics.scenarios_with_expected_outcome == 1
        assert metrics.accuracy_pct == 100.0

    def test_mixed_batch_accuracy(self, calculator: MetricsCalculator) -> None:
        results = [
            _make_result("ok1", outcome="APPROVE", expected_outcome="APPROVE"),
            _make_result("ok2", outcome="DECLINE", expected_outcome="DECLINE"),
            _make_result("bad", outcome="APPROVE", expected_outcome="DECLINE"),
        ]
        metrics = calculator.calculate(results)
        assert metrics.total_scenarios == 3
        assert metrics.correct_count == 2
        assert metrics.accuracy_pct == pytest.approx(66.67, abs=0.01)

    def test_to_dict_contains_all_fields(self, calculator: MetricsCalculator) -> None:
        metrics = calculator.calculate([_make_result()])
        d = metrics.to_dict()
        assert "total_scenarios" in d
        assert "accuracy_pct" in d
        assert "false_positive_count" in d
        assert "false_negative_count" in d
        assert "drift_event_count" in d

    def test_to_json_is_valid_json(self, calculator: MetricsCalculator) -> None:
        import json
        metrics = calculator.calculate([_make_result()])
        json_str = metrics.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_save_writes_file(self, calculator: MetricsCalculator, tmp_path) -> None:
        metrics = calculator.calculate([_make_result()])
        output_path = tmp_path / "metrics.json"
        metrics.save(output_path)
        assert output_path.exists()
        import json
        data = json.loads(output_path.read_text())
        assert data["total_scenarios"] == 1
