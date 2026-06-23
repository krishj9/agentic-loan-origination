"""Metrics calculation for evaluation harness batch runs (P6-T6).

Computes from a list of RunResult objects:
  - Accuracy percentage (correctly predicted decision outcomes / total).
  - False-positive count  (model APPROVED when expected DECLINE/REFER).
  - False-negative count  (model DECLINED when expected APPROVE).
  - Drift event count     (scenarios flagged with a drift event by DriftDetector).

All calculations are pure functions of the run results — no I/O, no side effects.
The summary is emitted to stdout as structured JSON and can be written to a file.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from evaluation.log import get_logger

if TYPE_CHECKING:
    from evaluation.replay.runner import RunResult

logger = get_logger(__name__)


@dataclass
class EvaluationMetrics:
    """Aggregated metrics for a batch evaluation run.

    Attributes:
        total_scenarios:   Total number of scenarios executed.
        accuracy_pct:      Percentage of scenarios where the predicted decision
                           outcome matches the expected outcome (0.0–100.0).
        correct_count:     Number of scenarios with correct decision outcome.
        false_positive_count: Scenarios approved by the model that should have
                           been declined or referred (model too lenient).
        false_negative_count: Scenarios declined by the model that should have
                           been approved (model too strict).
        drift_event_count: Number of scenarios flagged as drift events.
        scenarios_with_expected_outcome: Scenarios that had an expected_decision_outcome
                           defined (subset of total used for accuracy/FP/FN calc).
    """

    total_scenarios: int
    accuracy_pct: float
    correct_count: int
    false_positive_count: int
    false_negative_count: int
    drift_event_count: int
    scenarios_with_expected_outcome: int

    def to_dict(self) -> dict[str, Any]:
        """Return the metrics as a plain dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialise the metrics to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, output_path: Path) -> None:
        """Write the metrics JSON to *output_path*, creating parent dirs."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_json())
        logger.info("Metrics saved", extra={"output_path": str(output_path)})


class MetricsCalculator:
    """Calculate evaluation metrics from a list of RunResult objects (P6-T6).

    The calculator is stateless — call :meth:`calculate` with any list of
    results to get an :class:`EvaluationMetrics` instance.

    Decision outcome semantics
    --------------------------
    * **APPROVE** is the positive class for FP/FN calculations.
    * **False Positive**: model returned APPROVE; expected was DECLINE or REFER.
    * **False Negative**: model returned DECLINE; expected was APPROVE.
    * Scenarios missing ``expected_decision_outcome`` are excluded from
      accuracy/FP/FN calculations (but counted in ``total_scenarios``).

    Drift event counting
    --------------------
    A result is counted as a drift event when ``RunResult.drift_detected`` is
    ``True``.  :class:`~evaluation.replay.drift.DriftDetector` sets this flag
    before results are passed to the calculator.
    """

    def calculate(
        self,
        results: "list[RunResult]",
    ) -> EvaluationMetrics:
        """Compute metrics from execution results.

        Args:
            results: List of RunResult objects from BatchRunner.

        Returns:
            EvaluationMetrics dataclass with all computed metrics.
        """
        total = len(results)
        correct = 0
        fp = 0
        fn = 0
        drift_count = 0
        with_expected = 0

        for result in results:
            # Drift events
            if getattr(result, "drift_detected", False):
                drift_count += 1

            expected_outcome = result.scenario.expected_decision_outcome
            if expected_outcome is None:
                continue  # cannot evaluate accuracy without expectation

            with_expected += 1

            # Extract actual outcome from trace final state
            actual_outcome = self._extract_actual_outcome(result)
            if actual_outcome is None:
                continue  # execution failed / outcome not captured

            actual_outcome_norm = actual_outcome.upper()
            expected_outcome_norm = expected_outcome.upper()

            if actual_outcome_norm == expected_outcome_norm:
                correct += 1
            else:
                # FP: model approved something it should have declined/referred
                if actual_outcome_norm == "APPROVE" and expected_outcome_norm in ("DECLINE", "REFER"):
                    fp += 1
                # FN: model declined something it should have approved
                elif actual_outcome_norm == "DECLINE" and expected_outcome_norm == "APPROVE":
                    fn += 1

        accuracy_pct = (correct / with_expected * 100.0) if with_expected > 0 else 0.0

        metrics = EvaluationMetrics(
            total_scenarios=total,
            accuracy_pct=round(accuracy_pct, 2),
            correct_count=correct,
            false_positive_count=fp,
            false_negative_count=fn,
            drift_event_count=drift_count,
            scenarios_with_expected_outcome=with_expected,
        )

        logger.info(
            "Metrics calculated",
            extra={
                "total": total,
                "accuracy_pct": metrics.accuracy_pct,
                "fp": fp,
                "fn": fn,
                "drift_events": drift_count,
            },
        )

        return metrics

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_actual_outcome(result: "RunResult") -> str | None:
        """Extract the actual decision outcome from a RunResult's trace.

        Args:
            result: RunResult to extract from.

        Returns:
            Outcome string (e.g. "APPROVE") or None if unavailable.
        """
        if result.trace is None or result.trace.final_state is None:
            return None
        decision = result.trace.final_state.fields.get("decision")
        if isinstance(decision, dict):
            return decision.get("outcome")
        # Handle Pydantic model serialised as a nested object
        if hasattr(decision, "outcome"):
            return str(decision.outcome)
        return None
