"""Tests for execution trace models and serialization."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from evaluation.replay.trace import (
    ExecutionStatus,
    ExecutionTrace,
    NodeExecution,
    StateSnapshot,
    ToolInvocation,
    TraceSerializer,
)


class TestStateSnapshot:
    """Tests for StateSnapshot model."""

    def test_create_snapshot(self):
        """Test creating a state snapshot."""
        snapshot = StateSnapshot(
            timestamp=datetime.utcnow(),
            application_id="app_001",
            fields={"application_id": "app_001", "user_id": "user_123"},
        )

        assert snapshot.application_id == "app_001"
        assert "application_id" in snapshot.fields
        assert snapshot.fields["user_id"] == "user_123"

    def test_snapshot_serialization(self):
        """Test snapshot serialization to dict."""
        snapshot = StateSnapshot(
            application_id="app_001",
            fields={"test": "value"},
        )

        data = snapshot.model_dump(by_alias=True)
        assert "applicationId" in data
        assert "fields" in data


class TestToolInvocation:
    """Tests for ToolInvocation model."""

    def test_create_tool_invocation(self):
        """Test creating a tool invocation record."""
        invocation = ToolInvocation(
            tool_name="risk_engine.evaluate",
            invoked_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            inputs={"applicantId": "app_001"},
            outputs={"riskProfile": "PRIME"},
        )

        assert invocation.tool_name == "risk_engine.evaluate"
        assert invocation.status == ExecutionStatus.SUCCESS
        assert invocation.inputs["applicantId"] == "app_001"

    def test_tool_invocation_with_duration(self):
        """Test tool invocation with duration calculation."""
        invoked_at = datetime.utcnow()
        invocation = ToolInvocation(
            tool_name="test_tool",
            invoked_at=invoked_at,
            status=ExecutionStatus.SUCCESS,
            duration_ms=150.5,
        )

        assert invocation.duration_ms == 150.5

    def test_tool_invocation_failure(self):
        """Test tool invocation with failure status."""
        invocation = ToolInvocation(
            tool_name="failing_tool",
            invoked_at=datetime.utcnow(),
            status=ExecutionStatus.FAILED,
            error_message="Tool execution failed",
        )

        assert invocation.status == ExecutionStatus.FAILED
        assert invocation.error_message == "Tool execution failed"
        assert invocation.outputs is None


class TestNodeExecution:
    """Tests for NodeExecution model."""

    def test_create_node_execution(self):
        """Test creating a node execution record."""
        node_exec = NodeExecution(
            node_name="run_risk",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )

        assert node_exec.node_name == "run_risk"
        assert node_exec.status == ExecutionStatus.SUCCESS

    def test_node_execution_with_snapshots(self):
        """Test node execution with before/after state snapshots."""
        node_exec = NodeExecution(
            node_name="test_node",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            state_before=StateSnapshot(
                application_id="app_001",
                fields={"count": 5},
            ),
            state_after=StateSnapshot(
                application_id="app_001",
                fields={"count": 7},
            ),
            state_before_count=5,
            state_after_count=7,
        )

        assert node_exec.state_before is not None
        assert node_exec.state_after is not None
        assert node_exec.state_before_count == 5
        assert node_exec.state_after_count == 7

    def test_node_execution_with_tool_invocations(self):
        """Test node execution with tool invocations."""
        tool_invocation = ToolInvocation(
            tool_name="test_tool",
            invoked_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )

        node_exec = NodeExecution(
            node_name="test_node",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            tool_invocations=[tool_invocation],
        )

        assert len(node_exec.tool_invocations) == 1
        assert node_exec.tool_invocations[0].tool_name == "test_tool"


class TestExecutionTrace:
    """Tests for ExecutionTrace model."""

    def test_create_execution_trace(self):
        """Test creating an execution trace."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.RUNNING,
        )

        assert trace.trace_id == "trace_001"
        assert trace.scenario_id == "scenario_001"
        assert trace.status == ExecutionStatus.RUNNING

    def test_execution_trace_with_nodes(self):
        """Test execution trace with node executions."""
        node1 = NodeExecution(
            node_name="node1",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )
        node2 = NodeExecution(
            node_name="node2",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )

        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            node_executions=[node1, node2],
            nodes_executed_count=2,
        )

        assert len(trace.node_executions) == 2
        assert trace.nodes_executed_count == 2

    def test_execution_trace_with_correlation_id(self):
        """Test execution trace with correlation ID."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            correlation_id="corr_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.RUNNING,
        )

        assert trace.correlation_id == "corr_001"

    def test_execution_trace_completed(self):
        """Test completed execution trace with timing."""
        started_at = datetime.utcnow()
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=started_at,
            status=ExecutionStatus.SUCCESS,
            completed_at=datetime.utcnow(),
            duration_ms=1500.0,
            nodes_executed_count=5,
            tools_invoked_count=3,
        )

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.completed_at is not None
        assert trace.duration_ms == 1500.0
        assert trace.nodes_executed_count == 5
        assert trace.tools_invoked_count == 3


class TestTraceSerializer:
    """Tests for TraceSerializer."""

    def test_serialize_trace(self):
        """Test serializing trace to dictionary."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )

        data = TraceSerializer.serialize(trace)

        assert isinstance(data, dict)
        assert data["traceId"] == "trace_001"
        assert data["scenarioId"] == "scenario_001"

    def test_serialize_to_json(self):
        """Test serializing trace to JSON string."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )

        json_str = TraceSerializer.to_json(trace)

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["traceId"] == "trace_001"

    def test_save_trace_to_file(self):
        """Test saving trace to JSON file."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "trace.json"
            TraceSerializer.save(trace, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert data["traceId"] == "trace_001"

    def test_serialize_nested_structures(self):
        """Test serializing trace with nested structures."""
        node_exec = NodeExecution(
            node_name="test_node",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            tool_invocations=[
                ToolInvocation(
                    tool_name="test_tool",
                    invoked_at=datetime.utcnow(),
                    status=ExecutionStatus.SUCCESS,
                )
            ],
        )

        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            node_executions=[node_exec],
        )

        json_str = TraceSerializer.to_json(trace)
        data = json.loads(json_str)

        assert len(data["nodeExecutions"]) == 1
        assert data["nodeExecutions"][0]["nodeName"] == "test_node"
        assert len(data["nodeExecutions"][0]["toolInvocations"]) == 1

    def test_serialize_with_state_snapshots(self):
        """Test serializing trace with state snapshots."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            scenario_id="scenario_001",
            started_at=datetime.utcnow(),
            status=ExecutionStatus.SUCCESS,
            initial_state=StateSnapshot(
                application_id="app_001",
                fields={"initial": "state"},
            ),
            final_state=StateSnapshot(
                application_id="app_001",
                fields={"final": "state"},
            ),
        )

        json_str = TraceSerializer.to_json(trace)
        data = json.loads(json_str)

        assert "initialState" in data
        assert data["initialState"]["fields"]["initial"] == "state"
        assert "finalState" in data
        assert data["finalState"]["fields"]["final"] == "state"
