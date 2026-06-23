"""Batch runner for executing multiple scenarios with result aggregation."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.log import get_logger
from evaluation.replay.engine import ReplayEngine
from evaluation.replay.trace import ExecutionStatus, ExecutionTrace, TraceSerializer
from evaluation.scenarios import EndToEndScenario

logger = get_logger(__name__)


@dataclass
class RunResult:
    """Result of executing a single scenario.

    Combines the scenario, execution trace, and validation results.
    ``drift_detected`` is set by :class:`~evaluation.replay.drift.DriftDetector`
    after the batch run completes.
    """

    scenario_id: str
    scenario: EndToEndScenario
    trace: ExecutionTrace
    validation_passed: bool
    validation_errors: list[str]
    duration_ms: float
    drift_detected: bool = False


class BatchRunner:
    """Batch execution runner for multiple scenarios.

    Executes scenarios sequentially or in parallel, aggregates results,
    and produces summary reports.
    """

    def __init__(
        self,
        replay_engine: ReplayEngine | None = None,
        max_workers: int = 1,
    ) -> None:
        """Initialize batch runner.

        Args:
            replay_engine: ReplayEngine instance (creates one if None)
            max_workers: Maximum parallel workers (default: 1 for sequential)
        """
        self.replay_engine = replay_engine or ReplayEngine(enable_tracing=True)
        self.max_workers = max_workers
        logger.info(
            "BatchRunner initialized",
            extra={"max_workers": max_workers},
        )

    def run_scenarios(
        self,
        scenarios: list[EndToEndScenario],
        validate: bool = True,
    ) -> list[RunResult]:
        """Execute multiple scenarios in batch.

        Args:
            scenarios: List of scenarios to execute
            validate: Whether to validate results against expected outcomes (default: True)

        Returns:
            List of RunResult objects with execution details
        """
        logger.info(
            "Starting batch scenario execution",
            extra={
                "scenario_count": len(scenarios),
                "validate": validate,
                "max_workers": self.max_workers,
            },
        )

        results: list[RunResult] = []

        if self.max_workers == 1:
            # Sequential execution
            for scenario in scenarios:
                result = self._execute_and_validate(scenario, validate)
                results.append(result)
        else:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_scenario = {
                    executor.submit(self._execute_and_validate, scenario, validate): scenario
                    for scenario in scenarios
                }

                for future in as_completed(future_to_scenario):
                    result = future.result()
                    results.append(result)

        logger.info(
            "Batch scenario execution completed",
            extra={
                "total_scenarios": len(results),
                "passed": sum(1 for r in results if r.validation_passed),
                "failed": sum(1 for r in results if not r.validation_passed),
            },
        )

        return results

    def run_from_directory(
        self,
        scenarios_dir: Path,
        output_dir: Path | None = None,
        validate: bool = True,
    ) -> list[RunResult]:
        """Load and execute scenarios from a directory.

        Args:
            scenarios_dir: Directory containing scenario JSON files
            output_dir: Optional directory to save traces (uses scenarios_dir/traces if None)
            validate: Whether to validate results

        Returns:
            List of RunResult objects
        """
        logger.info(
            "Loading scenarios from directory",
            extra={"scenarios_dir": str(scenarios_dir)},
        )

        # Load scenarios
        scenarios = []
        for scenario_file in scenarios_dir.glob("*.json"):
            try:
                with open(scenario_file) as f:
                    data = json.load(f)
                scenario = EndToEndScenario(**data)
                scenarios.append(scenario)
            except Exception as e:
                logger.warning(
                    "Failed to load scenario",
                    extra={
                        "file": str(scenario_file),
                        "error": str(e),
                    },
                )

        logger.info(
            "Loaded scenarios",
            extra={"count": len(scenarios)},
        )

        # Execute scenarios
        results = self.run_scenarios(scenarios, validate=validate)

        # Save traces if output directory specified
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            for result in results:
                trace_path = output_dir / f"{result.scenario_id}_trace.json"
                TraceSerializer.save(result.trace, trace_path)
                logger.info(
                    "Saved trace",
                    extra={
                        "scenario_id": result.scenario_id,
                        "trace_path": str(trace_path),
                    },
                )

        return results

    def generate_report(
        self,
        results: list[RunResult],
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        """Generate summary report from batch execution results.

        Args:
            results: List of RunResult objects
            output_path: Optional path to save report JSON

        Returns:
            Report dictionary
        """
        total = len(results)
        passed = sum(1 for r in results if r.validation_passed)
        failed = total - passed

        # Calculate statistics
        total_duration_ms = sum(r.duration_ms for r in results)
        avg_duration_ms = total_duration_ms / total if total > 0 else 0

        # Group by status
        success_count = sum(
            1 for r in results if r.trace.status == ExecutionStatus.SUCCESS
        )
        failed_execution_count = sum(
            1 for r in results if r.trace.status == ExecutionStatus.FAILED
        )

        # Build report
        report = {
            "summary": {
                "total_scenarios": total,
                "validation_passed": passed,
                "validation_failed": failed,
                "success_rate": (passed / total * 100) if total > 0 else 0,
                "execution_success": success_count,
                "execution_failed": failed_execution_count,
            },
            "timing": {
                "total_duration_ms": total_duration_ms,
                "average_duration_ms": avg_duration_ms,
                "min_duration_ms": min((r.duration_ms for r in results), default=0),
                "max_duration_ms": max((r.duration_ms for r in results), default=0),
            },
            "scenarios": [
                {
                    "scenario_id": r.scenario_id,
                    "validation_passed": r.validation_passed,
                    "validation_errors": r.validation_errors,
                    "execution_status": r.trace.status.value,
                    "nodes_executed": r.trace.nodes_executed_count,
                    "tools_invoked": r.trace.tools_invoked_count,
                    "duration_ms": r.duration_ms,
                }
                for r in results
            ],
        }

        # Save report if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(
                "Saved batch execution report",
                extra={"output_path": str(output_path)},
            )

        return report

    def _execute_and_validate(
        self,
        scenario: EndToEndScenario,
        validate: bool,
    ) -> RunResult:
        """Execute a single scenario and validate results.

        Args:
            scenario: Scenario to execute
            validate: Whether to validate results

        Returns:
            RunResult with execution and validation details
        """
        scenario_id = scenario.metadata.scenario_id

        logger.info(
            "Executing scenario",
            extra={"scenario_id": scenario_id},
        )

        # Execute scenario
        trace = self.replay_engine.execute_scenario(scenario)

        # Validate if requested
        validation_passed = True
        validation_errors: list[str] = []

        if validate:
            validation_passed, validation_errors = self._validate_execution(
                scenario, trace
            )

        return RunResult(
            scenario_id=scenario_id,
            scenario=scenario,
            trace=trace,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            duration_ms=trace.duration_ms or 0,
        )

    def _validate_execution(
        self,
        scenario: EndToEndScenario,
        trace: ExecutionTrace,
    ) -> tuple[bool, list[str]]:
        """Validate execution results against expected outcomes.

        Args:
            scenario: Original scenario with expected outcomes
            trace: Execution trace with actual results

        Returns:
            Tuple of (passed, errors) where errors is a list of validation error messages
        """
        errors: list[str] = []

        # Check execution status
        if trace.status != ExecutionStatus.SUCCESS:
            errors.append(f"Execution failed: {trace.error_message}")
            return (False, errors)

        # Validate final state exists
        if trace.final_state is None:
            errors.append("No final state captured")
            return (False, errors)

        final_state = trace.final_state.fields

        # Validate expected risk profile
        if scenario.expected_risk_profile:
            risk_response = final_state.get("risk_response")
            if risk_response:
                actual_profile = risk_response.get("riskProfile")
                expected_profile = scenario.expected_risk_profile.value
                if actual_profile != expected_profile:
                    errors.append(
                        f"Risk profile mismatch: expected {expected_profile}, got {actual_profile}"
                    )

        # Validate expected decision outcome
        if scenario.expected_decision_outcome:
            decision = final_state.get("decision")
            if decision:
                actual_outcome = decision.get("outcome")
                expected_outcome = scenario.expected_decision_outcome
                if actual_outcome != expected_outcome:
                    errors.append(
                        f"Decision outcome mismatch: expected {expected_outcome}, got {actual_outcome}"
                    )

        # Validate expected compliance action
        if scenario.expected_compliance_action:
            compliance_result = final_state.get("compliance_result")
            if compliance_result:
                actual_action = compliance_result.get("recommendedAction")
                expected_action = scenario.expected_compliance_action
                if actual_action != expected_action:
                    errors.append(
                        f"Compliance action mismatch: expected {expected_action}, got {actual_action}"
                    )

        passed = len(errors) == 0

        if passed:
            logger.info(
                "Validation passed",
                extra={"scenario_id": scenario.metadata.scenario_id},
            )
        else:
            logger.warning(
                "Validation failed",
                extra={
                    "scenario_id": scenario.metadata.scenario_id,
                    "errors": errors,
                },
            )

        return (passed, errors)
