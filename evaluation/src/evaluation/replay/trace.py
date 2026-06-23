"""Execution trace models for capturing LangGraph execution details.

Provides structured models for:
- State snapshots at each node
- Tool invocations with inputs/outputs
- Node execution timing and status
- Complete execution trace serialization
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(StrEnum):
    """Status of a node or tool execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StateSnapshot(BaseModel):
    """Snapshot of LangGraph state at a specific point in execution.

    Captures the full state dict with all populated fields.
    Uses canonical schemas where applicable.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "timestamp": "2026-06-23T12:00:00Z",
                "applicationId": "app_001",
                "fields": {
                    "application_id": "app_001",
                    "user_id": "user_123",
                    "application": {"applicantName": "Jane Smith"},
                },
            }
        },
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when snapshot was taken",
    )
    application_id: str | None = Field(
        default=None,
        alias="applicationId",
        description="Application ID for correlation",
    )
    fields: dict[str, Any] = Field(
        description="State dictionary at this point in execution"
    )


class ToolInvocation(BaseModel):
    """Record of a single tool invocation during execution.

    Captures tool name, inputs, outputs, and timing.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "toolName": "risk_engine.evaluate",
                "invokedAt": "2026-06-23T12:00:00Z",
                "completedAt": "2026-06-23T12:00:01Z",
                "status": "SUCCESS",
                "inputs": {"applicantId": "app_001", "annualIncome": "85000"},
                "outputs": {"riskProfile": "PRIME", "creditScore": 750},
            }
        },
    )

    tool_name: str = Field(
        alias="toolName",
        description="Name of the tool that was invoked",
    )
    invoked_at: datetime = Field(
        alias="invokedAt",
        description="UTC timestamp when tool was invoked",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="UTC timestamp when tool completed",
    )
    status: ExecutionStatus = Field(
        description="Execution status of the tool invocation"
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool input parameters",
    )
    outputs: dict[str, Any] | None = Field(
        default=None,
        description="Tool output result (None if failed)",
    )
    error_message: str | None = Field(
        default=None,
        alias="errorMessage",
        description="Error message if tool invocation failed",
    )
    duration_ms: float | None = Field(
        default=None,
        alias="durationMs",
        description="Execution duration in milliseconds",
    )


class NodeExecution(BaseModel):
    """Record of a single node execution in the LangGraph.

    Captures node name, state before/after, tool invocations, and timing.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "nodeName": "run_risk",
                "startedAt": "2026-06-23T12:00:00Z",
                "completedAt": "2026-06-23T12:00:01Z",
                "status": "SUCCESS",
                "stateBeforeCount": 5,
                "stateAfterCount": 7,
                "toolInvocations": [{"toolName": "risk_engine.evaluate"}],
            }
        },
    )

    node_name: str = Field(
        alias="nodeName",
        description="Name of the graph node that executed",
    )
    started_at: datetime = Field(
        alias="startedAt",
        description="UTC timestamp when node execution started",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="UTC timestamp when node execution completed",
    )
    status: ExecutionStatus = Field(
        description="Execution status of the node"
    )
    state_before: StateSnapshot | None = Field(
        default=None,
        alias="stateBefore",
        description="State snapshot before node execution",
    )
    state_after: StateSnapshot | None = Field(
        default=None,
        alias="stateAfter",
        description="State snapshot after node execution",
    )
    state_before_count: int = Field(
        default=0,
        alias="stateBeforeCount",
        description="Number of populated state fields before execution",
    )
    state_after_count: int = Field(
        default=0,
        alias="stateAfterCount",
        description="Number of populated state fields after execution",
    )
    tool_invocations: list[ToolInvocation] = Field(
        default_factory=list,
        alias="toolInvocations",
        description="Tools invoked during this node execution",
    )
    error_message: str | None = Field(
        default=None,
        alias="errorMessage",
        description="Error message if node execution failed",
    )
    duration_ms: float | None = Field(
        default=None,
        alias="durationMs",
        description="Execution duration in milliseconds",
    )


class ExecutionTrace(BaseModel):
    """Complete execution trace for a scenario replay.

    Captures:
    - Scenario metadata
    - Initial and final state
    - All node executions with state transitions
    - All tool invocations
    - Overall timing and status
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "traceId": "trace_001",
                "scenarioId": "e2e_approve_001",
                "startedAt": "2026-06-23T12:00:00Z",
                "completedAt": "2026-06-23T12:00:10Z",
                "status": "SUCCESS",
                "nodeExecutions": [{"nodeName": "ingest_application"}],
            }
        },
    )

    trace_id: str = Field(
        alias="traceId",
        description="Unique identifier for this execution trace",
    )
    scenario_id: str = Field(
        alias="scenarioId",
        description="Scenario ID that was executed",
    )
    correlation_id: str | None = Field(
        default=None,
        alias="correlationId",
        description="Optional correlation ID for cross-system tracing",
    )
    started_at: datetime = Field(
        alias="startedAt",
        description="UTC timestamp when execution started",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="UTC timestamp when execution completed",
    )
    status: ExecutionStatus = Field(
        description="Overall execution status"
    )
    initial_state: StateSnapshot | None = Field(
        default=None,
        alias="initialState",
        description="State at the beginning of execution",
    )
    final_state: StateSnapshot | None = Field(
        default=None,
        alias="finalState",
        description="State at the end of execution",
    )
    node_executions: list[NodeExecution] = Field(
        default_factory=list,
        alias="nodeExecutions",
        description="Ordered list of node executions",
    )
    error_message: str | None = Field(
        default=None,
        alias="errorMessage",
        description="Error message if execution failed",
    )
    duration_ms: float | None = Field(
        default=None,
        alias="durationMs",
        description="Total execution duration in milliseconds",
    )
    nodes_executed_count: int = Field(
        default=0,
        alias="nodesExecutedCount",
        description="Total number of nodes executed",
    )
    tools_invoked_count: int = Field(
        default=0,
        alias="toolsInvokedCount",
        description="Total number of tools invoked",
    )


class TraceSerializer:
    """Serializer for execution traces to structured JSON.

    Handles custom types (Decimal, datetime, Pydantic models) and
    produces clean, readable JSON output.
    """

    @staticmethod
    def serialize(trace: ExecutionTrace) -> dict[str, Any]:
        """Serialize execution trace to dictionary.

        Args:
            trace: ExecutionTrace to serialize

        Returns:
            Dictionary suitable for JSON serialization
        """
        return trace.model_dump(by_alias=True, mode="json")

    @staticmethod
    def to_json(trace: ExecutionTrace, indent: int = 2) -> str:
        """Serialize execution trace to JSON string.

        Args:
            trace: ExecutionTrace to serialize
            indent: JSON indentation level (default: 2)

        Returns:
            JSON string representation
        """
        data = TraceSerializer.serialize(trace)
        return json.dumps(data, indent=indent, default=TraceSerializer._json_encoder)

    @staticmethod
    def save(trace: ExecutionTrace, output_path: Path, indent: int = 2) -> None:
        """Save execution trace to JSON file.

        Args:
            trace: ExecutionTrace to save
            output_path: Path to output file
            indent: JSON indentation level (default: 2)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                TraceSerializer.serialize(trace),
                f,
                indent=indent,
                default=TraceSerializer._json_encoder,
            )

    @staticmethod
    def _json_encoder(obj: Any) -> Any:
        """Custom JSON encoder for non-standard types.

        Args:
            obj: Object to encode

        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat() + "Z" if obj.tzinfo is None else obj.isoformat()
        if isinstance(obj, BaseModel):
            return obj.model_dump(by_alias=True, mode="json")
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
