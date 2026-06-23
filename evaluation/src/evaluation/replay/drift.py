"""Drift detection for the deterministic mock risk engine (P6-T7).

Compares the risk profile observed in each execution trace against the
deterministic classification rules defined in ``tools/config/risk_policy.yaml``.

A **drift event** is raised when:
  * A trace completed successfully *and*
  * The final state contains a ``risk_response`` with a ``riskProfile`` field *and*
  * The expected profile (derived from the scenario's income + utilization via
    the same rules the engine applies) differs from the observed profile.

The policy YAML is the single source of truth (design §10.3, requirements §7.3).
The detector reads it once on construction and applies the same PRIME → SUBPRIME →
NEAR_PRIME classification order used by the engine so the comparison is exact.

Usage
-----
::

    from evaluation.replay.drift import DriftDetector
    from evaluation.replay.runner import BatchRunner, RunResult

    detector = DriftDetector()
    results: list[RunResult] = batch_runner.run_scenarios(scenarios)
    flagged = detector.annotate(results)   # mutates each result in-place
    report  = detector.build_report(results)

Drift log lines carry ``event_type = "DRIFT_DETECTED"`` so the CloudWatch metric
filter in ``infra/modules/observability/main.tf`` picks them up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from evaluation.log import get_logger

if TYPE_CHECKING:
    from evaluation.replay.runner import RunResult

logger = get_logger(__name__)

# Path to the policy YAML used by the risk engine.
_DEFAULT_POLICY_PATH = (
    Path(__file__).parent.parent.parent.parent.parent.parent
    / "tools" / "config" / "risk_policy.yaml"
)


@dataclass
class DriftEvent:
    """Record of a single drift event.

    Attributes:
        scenario_id:       Which scenario drifted.
        expected_profile:  Profile predicted by the policy rules.
        observed_profile:  Profile actually returned by the risk engine.
        annual_income:     Input annual income used for classification.
        debt_utilization:  Input debt utilization used for classification.
        reason:            Human-readable explanation.
    """

    scenario_id: str
    expected_profile: str
    observed_profile: str
    annual_income: str
    debt_utilization: str
    reason: str


@dataclass
class DriftReport:
    """Aggregated drift detection report for a batch run.

    Attributes:
        total_evaluated:   Scenarios checked for drift.
        drift_count:       Number of scenarios with drift detected.
        clean_count:       Scenarios with no drift.
        drift_rate_pct:    drift_count / total_evaluated * 100.
        events:            Full list of individual drift events.
    """

    total_evaluated: int
    drift_count: int
    clean_count: int
    drift_rate_pct: float
    events: list[DriftEvent] = field(default_factory=list)


class DriftDetector:
    """Compare observed risk profiles against deterministic policy rules (P6-T7).

    The detector loads the risk policy YAML once and applies the same
    classification logic as the engine (PRIME → SUBPRIME → NEAR_PRIME) to
    the scenario's financial inputs.  Any deviation between the expected
    policy-derived profile and the observed trace profile is flagged.

    Args:
        policy_path: Path to ``risk_policy.yaml``.  Defaults to the path
                     relative to this file inside the repository.
    """

    def __init__(self, policy_path: Path | None = None) -> None:
        self._policy_path = policy_path or _DEFAULT_POLICY_PATH
        self._bands = self._load_bands()

    # ── Public API ────────────────────────────────────────────────────────────

    def annotate(self, results: list[RunResult]) -> list[RunResult]:
        """Annotate each RunResult with ``drift_detected`` flag (mutates in-place).

        Scenarios that lack financial data or did not complete successfully are
        skipped (``drift_detected`` is left as ``False``).

        Args:
            results: List of RunResult objects to annotate.

        Returns:
            The same list (mutated in-place) for chaining.
        """
        for result in results:
            event = self._check_result(result)
            if event is not None:
                result.drift_detected = True
                logger.warning(
                    "Drift detected",
                    extra={
                        "event_type": "DRIFT_DETECTED",
                        "scenario_id": event.scenario_id,
                        "expected_profile": event.expected_profile,
                        "observed_profile": event.observed_profile,
                        "annual_income": event.annual_income,
                        "debt_utilization": event.debt_utilization,
                        "reason": event.reason,
                    },
                )
            else:
                result.drift_detected = False
        return results

    def build_report(self, results: list[RunResult]) -> DriftReport:
        """Build a DriftReport from annotated results.

        Call :meth:`annotate` first so that ``drift_detected`` flags are set.

        Args:
            results: Annotated RunResult list.

        Returns:
            DriftReport with counts and individual drift events.
        """
        events: list[DriftEvent] = []
        evaluated = 0

        for result in results:
            event = self._check_result(result)
            if event is not None:
                evaluated += 1
                events.append(event)
            elif self._has_risk_data(result):
                evaluated += 1

        drift_count = len(events)
        clean_count = evaluated - drift_count
        drift_rate_pct = (drift_count / evaluated * 100.0) if evaluated > 0 else 0.0

        report = DriftReport(
            total_evaluated=evaluated,
            drift_count=drift_count,
            clean_count=clean_count,
            drift_rate_pct=round(drift_rate_pct, 2),
            events=events,
        )

        logger.info(
            "Drift report built",
            extra={
                "total_evaluated": evaluated,
                "drift_count": drift_count,
                "drift_rate_pct": report.drift_rate_pct,
            },
        )

        return report

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_bands(self) -> dict[str, Any]:
        """Load band thresholds from the policy YAML.

        Returns:
            Dictionary of band configurations keyed by profile name.

        Raises:
            FileNotFoundError: If the policy YAML is not found.
        """
        import yaml  # deferred import — optional dep in evaluation package

        if not self._policy_path.exists():
            raise FileNotFoundError(
                f"risk_policy.yaml not found at {self._policy_path}. "
                "Ensure the tools/ directory is present in the repository."
            )
        with open(self._policy_path) as f:
            data = yaml.safe_load(f)
        return data.get("bands", {})

    def _classify(self, annual_income: Decimal, debt_utilization: Decimal) -> str:
        """Apply policy band rules and return the expected risk profile string.

        Mirrors the classification order in ``tools/src/tools/risk_engine/engine.py``:
          1. PRIME   (income > threshold AND utilization < threshold)
          2. SUBPRIME (income < threshold OR utilization > threshold)
          3. NEAR_PRIME (everything else)

        Args:
            annual_income:   Annualised gross income in USD.
            debt_utilization: Aggregate debt utilisation ratio (0.0–1.0).

        Returns:
            Profile name string: "PRIME", "SUBPRIME", or "NEAR_PRIME".
        """
        prime = self._bands.get("PRIME", {})
        subprime = self._bands.get("SUBPRIME", {})

        prime_income_min = prime.get("income_min_exclusive")
        prime_util_max = prime.get("utilization_max_exclusive")

        is_prime = (
            prime_income_min is not None
            and prime_util_max is not None
            and annual_income > Decimal(str(prime_income_min))
            and debt_utilization < Decimal(str(prime_util_max))
        )
        if is_prime:
            return "PRIME"

        sub_income_max = subprime.get("income_max_exclusive")
        sub_util_min = subprime.get("utilization_min_exclusive")

        is_subprime = (
            (sub_income_max is not None and annual_income < Decimal(str(sub_income_max)))
            or (sub_util_min is not None and debt_utilization > Decimal(str(sub_util_min)))
        )
        if is_subprime:
            return "SUBPRIME"

        return "NEAR_PRIME"

    def _extract_financials(
        self, result: RunResult
    ) -> tuple[Decimal, Decimal] | None:
        """Extract annual_income and debt_utilization from the scenario.

        Returns:
            Tuple (annual_income, debt_utilization) or None if unavailable.
        """
        try:
            app = result.scenario.canonical_application
            return Decimal(str(app.annual_income)), Decimal(str(app.debt_utilization))
        except (AttributeError, TypeError, ValueError):
            return None

    def _extract_observed_profile(self, result: RunResult) -> str | None:
        """Extract the risk profile from the trace final state.

        Returns:
            Profile string or None if unavailable.
        """
        if result.trace is None or result.trace.final_state is None:
            return None
        risk_response = result.trace.final_state.fields.get("risk_response")
        if isinstance(risk_response, dict):
            return risk_response.get("riskProfile")
        if hasattr(risk_response, "risk_profile"):
            return str(risk_response.risk_profile)
        return None

    def _has_risk_data(self, result: RunResult) -> bool:
        """Return True if the result has enough data to evaluate drift."""
        from evaluation.replay.trace import ExecutionStatus
        return (
            result.trace is not None
            and result.trace.status == ExecutionStatus.SUCCESS
            and self._extract_financials(result) is not None
            and self._extract_observed_profile(result) is not None
        )

    def _check_result(self, result: RunResult) -> DriftEvent | None:
        """Check a single result for drift.

        Args:
            result: RunResult to check.

        Returns:
            DriftEvent if drift is detected, else None.
        """
        from evaluation.replay.trace import ExecutionStatus

        # Only check successfully completed executions
        if result.trace is None or result.trace.status != ExecutionStatus.SUCCESS:
            return None

        financials = self._extract_financials(result)
        if financials is None:
            return None

        annual_income, debt_utilization = financials
        observed_profile = self._extract_observed_profile(result)
        if observed_profile is None:
            return None

        # If a risk_profile override was set on the scenario, skip drift check:
        # the engine intentionally uses the override, so there is no drift.
        try:
            app = result.scenario.canonical_application
            if getattr(app, "risk_profile", None) is not None:
                return None
        except AttributeError:
            pass

        expected_profile = self._classify(annual_income, debt_utilization)
        observed_profile_norm = observed_profile.upper()

        if expected_profile == observed_profile_norm:
            return None  # No drift

        return DriftEvent(
            scenario_id=result.scenario_id,
            expected_profile=expected_profile,
            observed_profile=observed_profile_norm,
            annual_income=str(annual_income),
            debt_utilization=str(debt_utilization),
            reason=(
                f"Policy rules classify income={annual_income}, "
                f"utilization={debt_utilization} as {expected_profile}, "
                f"but engine returned {observed_profile_norm}."
            ),
        )
