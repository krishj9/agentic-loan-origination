"""Tests for batch runner functionality."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from shared.schemas import DecisionOutcome, RiskProfile

from evaluation.replay.engine import ReplayEngine
from evaluation.replay.runner import BatchRunner, RunResult
from evaluation.replay.trace import ExecutionStatus
from evaluation.scenarios import ScenarioGenerator


class TestBatchRunner:
    """Tests for BatchRunner class."""

    @pytest.fixture
    def runner(self):
        """Provide a batch runner instance."""
        return BatchRunner(max_workers=1)

    @pytest.fixture
    def scenario_generator(self):
        """Provide a scenario generator."""
        return ScenarioGenerator(base_seed=42)

    def test_runner_initialization(self, runner):
        """Test that batch runner initializes correctly."""
        assert runner.replay_engine is not None
        assert runner.max_workers == 1

    def test_runner_with_custom_engine(self):
        """Test runner with custom replay engine."""
        custom_engine = ReplayEngine(enable_tracing=False)
        runner = BatchRunner(replay_engine=custom_engine, max_workers=2)

        assert runner.replay_engine == custom_engine
        assert runner.max_workers == 2

    @pytest.mark.skip(reason="Requires full agent implementation with mocked tools")
    def test_run_single_scenario(self, runner, scenario_generator):
        """Test running a single scenario.

        Skipped until tools are implemented.
        """
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_single",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=100,
        )

        results = runner.run_scenarios([scenario], validate=False)

        assert len(results) == 1
        assert results[0].scenario_id == "test_single"
        assert isinstance(results[0], RunResult)

    @pytest.mark.skip(reason="Requires full agent implementation with mocked tools")
    def test_run_multiple_scenarios(self, runner, scenario_generator):
        """Test running multiple scenarios in batch.

        Skipped until tools are implemented.
        """
        scenarios = [
            scenario_generator.generate_end_to_end_scenario(
                scenario_id=f"test_batch_{i}",
                risk_profile=RiskProfile.PRIME,
                expected_outcome=DecisionOutcome.APPROVE,
                seed=200 + i,
            )
            for i in range(3)
        ]

        results = runner.run_scenarios(scenarios, validate=False)

        assert len(results) == 3
        assert all(isinstance(r, RunResult) for r in results)

    def test_validate_execution_success(self, runner, scenario_generator):
        """Test validation logic for successful execution."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_validate_success",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=300,
        )

        # Create a mock trace with matching expected outcomes
        from datetime import datetime
        from evaluation.replay.trace import ExecutionTrace, StateSnapshot

        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="test_validate_success",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            final_state=StateSnapshot(
                application_id="app_001",
                fields={
                    "decision": {"outcome": DecisionOutcome.APPROVE.value},
                    "risk_response": {"riskProfile": RiskProfile.PRIME.value},
                    "compliance_result": {"recommendedAction": "APPROVE"},
                },
            ),
        )

        passed, errors = runner._validate_execution(scenario, trace)

        assert passed is True
        assert len(errors) == 0

    def test_validate_execution_failure(self, runner, scenario_generator):
        """Test validation logic for failed execution."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_validate_fail",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=400,
        )

        # Create a trace with execution failure
        from datetime import datetime
        from evaluation.replay.trace import ExecutionTrace

        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="test_validate_fail",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.FAILED,
            error_message="Execution failed",
        )

        passed, errors = runner._validate_execution(scenario, trace)

        assert passed is False
        assert len(errors) > 0
        assert "Execution failed" in errors[0]

    def test_validate_execution_mismatch(self, runner, scenario_generator):
        """Test validation with outcome mismatch."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_mismatch",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=500,
        )

        # Create trace with different outcome
        from datetime import datetime
        from evaluation.replay.trace import ExecutionTrace, StateSnapshot

        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="test_mismatch",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            final_state=StateSnapshot(
                application_id="app_001",
                fields={
                    "decision": {"outcome": DecisionOutcome.DECLINE.value},
                    "risk_response": {"riskProfile": RiskProfile.SUBPRIME.value},
                },
            ),
        )

        passed, errors = runner._validate_execution(scenario, trace)

        assert passed is False
        assert len(errors) > 0
        # Should have errors for both decision and risk profile mismatches
        assert any("Decision outcome mismatch" in err for err in errors)
        assert any("Risk profile mismatch" in err for err in errors)

    def test_generate_report(self, runner):
        """Test report generation from results."""
        # Create mock results
        from datetime import datetime
        from evaluation.replay.trace import ExecutionTrace

        results = [
            RunResult(
                scenario_id=f"scenario_{i}",
                scenario=None,  # Not needed for report
                trace=ExecutionTrace(
                    trace_id=f"trace_{i}",
                    scenario_id=f"scenario_{i}",
                    started_at=datetime.utcnow(),
                    status=ExecutionStatus.SUCCESS,
                    nodes_executed_count=5,
                    tools_invoked_count=3,
                ),
                validation_passed=i % 2 == 0,  # Alternate pass/fail
                validation_errors=[] if i % 2 == 0 else ["Error"],
                duration_ms=100.0 + i * 10,
            )
            for i in range(4)
        ]

        report = runner.generate_report(results)

        assert report["summary"]["total_scenarios"] == 4
        assert report["summary"]["validation_passed"] == 2
        assert report["summary"]["validation_failed"] == 2
        assert report["summary"]["success_rate"] == 50.0
        assert report["timing"]["total_duration_ms"] == 460.0
        assert len(report["scenarios"]) == 4

    def test_generate_report_saves_to_file(self, runner):
        """Test that report can be saved to file."""
        from datetime import datetime
        from evaluation.replay.trace import ExecutionTrace

        results = [
            RunResult(
                scenario_id="scenario_1",
                scenario=None,
                trace=ExecutionTrace(
                    trace_id="trace_1",
                    scenario_id="scenario_1",
                    started_at=datetime.utcnow(),
                    status=ExecutionStatus.SUCCESS,
                ),
                validation_passed=True,
                validation_errors=[],
                duration_ms=100.0,
            )
        ]

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            report = runner.generate_report(results, output_path=output_path)

            assert output_path.exists()

            with open(output_path) as f:
                saved_report = json.load(f)

            assert saved_report["summary"]["total_scenarios"] == 1

    def test_run_from_directory_no_scenarios(self, runner):
        """Test running from directory with no scenarios."""
        with TemporaryDirectory() as tmpdir:
            scenarios_dir = Path(tmpdir) / "scenarios"
            scenarios_dir.mkdir()

            results = runner.run_from_directory(scenarios_dir, validate=False)

            assert len(results) == 0

    @pytest.mark.skip(reason="Requires full agent implementation")
    def test_run_from_directory_with_scenarios(self, runner, scenario_generator):
        """Test loading and running scenarios from directory.

        Skipped until tools are implemented.
        """
        with TemporaryDirectory() as tmpdir:
            scenarios_dir = Path(tmpdir) / "scenarios"
            scenarios_dir.mkdir()

            # Generate and save scenarios
            for i in range(2):
                scenario = scenario_generator.generate_end_to_end_scenario(
                    scenario_id=f"test_dir_{i}",
                    risk_profile=RiskProfile.PRIME,
                    expected_outcome=DecisionOutcome.APPROVE,
                    seed=600 + i,
                )
                scenario_path = scenarios_dir / f"scenario_{i}.json"
                scenario_generator.save_scenario(scenario, scenario_path)

            # Run from directory
            output_dir = Path(tmpdir) / "traces"
            results = runner.run_from_directory(
                scenarios_dir,
                output_dir=output_dir,
                validate=False,
            )

            assert len(results) == 2
            assert output_dir.exists()

    def test_report_statistics(self, runner):
        """Test report statistics calculation."""
        from datetime import datetime
        from evaluation.replay.trace import ExecutionTrace

        results = [
            RunResult(
                scenario_id=f"scenario_{i}",
                scenario=None,
                trace=ExecutionTrace(
                    trace_id=f"trace_{i}",
                    scenario_id=f"scenario_{i}",
                    started_at=datetime.utcnow(),
                    status=ExecutionStatus.SUCCESS,
                ),
                validation_passed=True,
                validation_errors=[],
                duration_ms=100.0 * (i + 1),
            )
            for i in range(5)
        ]

        report = runner.generate_report(results)

        # Check statistics
        assert report["summary"]["success_rate"] == 100.0
        assert report["timing"]["min_duration_ms"] == 100.0
        assert report["timing"]["max_duration_ms"] == 500.0
        assert report["timing"]["average_duration_ms"] == 300.0
