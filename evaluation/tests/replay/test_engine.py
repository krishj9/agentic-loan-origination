"""Tests for replay engine execution.

Note: These tests require the agents package with LangGraph supervisor.
They test the integration between scenarios and the graph execution.
"""

import pytest
from shared.schemas import DecisionOutcome, RiskProfile

from evaluation.replay.engine import ReplayEngine
from evaluation.replay.trace import ExecutionStatus
from evaluation.scenarios import ScenarioGenerator


class TestReplayEngine:
    """Tests for ReplayEngine class."""

    @pytest.fixture
    def engine(self):
        """Provide a replay engine instance."""
        return ReplayEngine(enable_tracing=True)

    @pytest.fixture
    def scenario_generator(self):
        """Provide a scenario generator."""
        return ScenarioGenerator(base_seed=42)

    def test_engine_initialization(self, engine):
        """Test that engine initializes correctly."""
        assert engine.enable_tracing is True
        assert engine.supervisor_graph is not None

    def test_engine_without_tracing(self):
        """Test engine initialization without tracing."""
        engine = ReplayEngine(enable_tracing=False)
        assert engine.enable_tracing is False

    def test_generate_trace_id(self, engine):
        """Test trace ID generation."""
        trace_id = engine._generate_trace_id("scenario_001", "corr_001")
        assert trace_id.startswith("trace_")
        assert len(trace_id) > 10

    def test_generate_correlation_id(self, engine):
        """Test correlation ID generation."""
        corr_id = engine._generate_correlation_id("scenario_001")
        assert corr_id.startswith("corr_scenario_001_")

    def test_build_initial_state(self, engine, scenario_generator):
        """Test building initial state from scenario."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_e2e",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=100,
        )

        initial_state = engine._build_initial_state(
            scenario, "trace_001", "corr_001"
        )

        assert initial_state["application_id"] == scenario.canonical_application.application_id
        assert initial_state["user_id"] == scenario.canonical_application.user_id
        assert initial_state["trace_id"] == "trace_001"
        assert initial_state["application"] == scenario.canonical_application
        assert initial_state["error"] is None
        assert initial_state["parse_failure_count"] == 0

    def test_sanitize_state_for_snapshot(self, engine, scenario_generator):
        """Test state sanitization for snapshots."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_sanitize",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=200,
        )

        state = engine._build_initial_state(scenario, "trace_001", "corr_001")
        sanitized = engine._sanitize_state_for_snapshot(state)

        # Should have converted Pydantic models to dicts
        assert isinstance(sanitized["application"], dict)
        assert "applicationId" in sanitized["application"]

    @pytest.mark.skip(reason="Requires full agent implementation with mocked tools")
    def test_execute_scenario_success(self, engine, scenario_generator):
        """Test successful scenario execution.

        This test is skipped because it requires:
        - Full LangGraph supervisor implementation
        - Mocked tool implementations
        - Proper subgraph setup

        When tools are implemented, this can be enabled.
        """
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_success",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=300,
        )

        trace = engine.execute_scenario(scenario)

        assert trace.scenario_id == "test_success"
        assert trace.status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED]
        assert trace.trace_id is not None
        assert trace.started_at is not None

    def test_execute_scenario_structure(self, engine, scenario_generator):
        """Test that execution produces proper trace structure."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_structure",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=400,
        )

        # Execute (will likely fail due to missing tools, but should produce trace)
        trace = engine.execute_scenario(scenario)

        # Verify trace structure
        assert trace.trace_id is not None
        assert trace.scenario_id == "test_structure"
        assert trace.started_at is not None
        assert trace.status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED]

        # Should have correlation ID
        assert trace.correlation_id is not None

    def test_execute_scenario_determinism(self, engine, scenario_generator):
        """Test that scenario execution is deterministic.

        Note: This tests trace structure determinism. Full execution
        determinism requires mocked tools.
        """
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_determinism",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=500,
        )

        # Generate initial state multiple times
        state1 = engine._build_initial_state(scenario, "trace_001", "corr_001")
        state2 = engine._build_initial_state(scenario, "trace_001", "corr_001")

        # Should produce identical initial states
        assert state1["application_id"] == state2["application_id"]
        assert state1["user_id"] == state2["user_id"]
        assert state1["application"] == state2["application"]


class TestReplayEngineStateManagement:
    """Tests for state management in replay engine."""

    @pytest.fixture
    def engine(self):
        return ReplayEngine(enable_tracing=True)

    @pytest.fixture
    def scenario_generator(self):
        return ScenarioGenerator(base_seed=42)

    def test_initial_state_has_required_fields(self, engine, scenario_generator):
        """Test that initial state contains all required LangGraph state fields."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_required",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=600,
        )

        state = engine._build_initial_state(scenario, "trace_001", "corr_001")

        # Required fields from LoanApplicationState
        required_fields = [
            "application_id",
            "user_id",
            "trace_id",
            "application",
            "document_inventory",
            "risk_request",
            "risk_response",
            "compliance_result",
            "decision",
            "error",
            "needs_manual_review",
            "parse_failure_count",
        ]

        for field in required_fields:
            assert field in state, f"Missing required field: {field}"

    def test_initial_state_none_values(self, engine, scenario_generator):
        """Test that uninitialized state fields are None."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_none",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=700,
        )

        state = engine._build_initial_state(scenario, "trace_001", "corr_001")

        # Fields that should be None initially
        assert state["risk_request"] is None
        assert state["risk_response"] is None
        assert state["compliance_result"] is None
        assert state["decision"] is None
        assert state["error"] is None
        assert state["decided_at"] is None

    def test_initial_state_from_canonical_application(self, engine, scenario_generator):
        """Test that initial state correctly maps canonical application."""
        scenario = scenario_generator.generate_end_to_end_scenario(
            scenario_id="test_mapping",
            risk_profile=RiskProfile.PRIME,
            expected_outcome=DecisionOutcome.APPROVE,
            seed=800,
        )

        state = engine._build_initial_state(scenario, "trace_001", "corr_001")

        # Application fields should match
        assert state["application"].application_id == scenario.canonical_application.application_id
        assert state["application"].user_id == scenario.canonical_application.user_id
        assert state["application"].applicant_name == scenario.canonical_application.applicant_name
        assert state["application"].annual_income == scenario.canonical_application.annual_income
