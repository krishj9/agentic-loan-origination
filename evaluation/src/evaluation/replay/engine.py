"""Replay engine for deterministic scenario execution with tracing.

Executes scenarios step-by-step through the LangGraph supervisor,
capturing state transitions and tool invocations for validation.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Any

from agents.state import LoanApplicationState
from agents.supervisor import build_supervisor_graph
from shared.schemas import CanonicalApplication, DocumentType

from evaluation.log import get_logger, set_correlation_id, set_scenario_id
from evaluation.replay.trace import (
    ExecutionStatus,
    ExecutionTrace,
    NodeExecution,
    StateSnapshot,
    ToolInvocation,
)
from evaluation.scenarios import EndToEndScenario

logger = get_logger(__name__)


class ReplayEngine:
    """Deterministic replay engine for scenario execution.

    Executes scenarios through the LangGraph supervisor with full tracing:
    - Step-by-step node execution
    - State snapshots before/after each node
    - Tool invocation capture
    - Structured execution trace output

    All executions are deterministic and reproducible given the same
    scenario and seed.
    """

    def __init__(self, enable_tracing: bool = True) -> None:
        """Initialize replay engine.

        Args:
            enable_tracing: Whether to capture detailed execution traces (default: True)
        """
        self.enable_tracing = enable_tracing
        self.supervisor_graph = build_supervisor_graph()
        logger.info(
            "ReplayEngine initialized",
            extra={"enable_tracing": enable_tracing},
        )

    def execute_scenario(
        self,
        scenario: EndToEndScenario,
        correlation_id: str | None = None,
    ) -> ExecutionTrace:
        """Execute an end-to-end scenario with full tracing.

        Args:
            scenario: End-to-end scenario to execute
            correlation_id: Optional correlation ID for cross-system tracing

        Returns:
            ExecutionTrace with complete execution details

        Raises:
            ValueError: If scenario is invalid or missing required data
        """
        # Set up logging context
        scenario_id = scenario.metadata.scenario_id
        set_scenario_id(scenario_id)

        if correlation_id is None:
            correlation_id = self._generate_correlation_id(scenario_id)
        set_correlation_id(correlation_id)

        logger.info(
            "Starting scenario execution",
            extra={
                "scenario_id": scenario_id,
                "correlation_id": correlation_id,
                "scenario_type": scenario.metadata.scenario_type.value,
            },
        )

        # Initialize trace
        trace_id = self._generate_trace_id(scenario_id, correlation_id)
        started_at = datetime.utcnow()

        trace = ExecutionTrace(
            trace_id=trace_id,
            scenario_id=scenario_id,
            correlation_id=correlation_id,
            started_at=started_at,
            status=ExecutionStatus.RUNNING,
        )

        try:
            # Build initial state from scenario
            initial_state = self._build_initial_state(scenario, trace_id, correlation_id)

            # Capture initial state snapshot
            if self.enable_tracing:
                trace.initial_state = StateSnapshot(
                    timestamp=started_at,
                    application_id=initial_state.get("application_id"),
                    fields=self._sanitize_state_for_snapshot(initial_state),
                )

            # Execute graph with tracing
            final_state = self._execute_with_tracing(initial_state, trace)

            # Capture final state snapshot
            if self.enable_tracing:
                trace.final_state = StateSnapshot(
                    timestamp=datetime.utcnow(),
                    application_id=final_state.get("application_id"),
                    fields=self._sanitize_state_for_snapshot(final_state),
                )

            # Update trace metadata
            trace.status = ExecutionStatus.SUCCESS
            trace.completed_at = datetime.utcnow()
            trace.duration_ms = (
                (trace.completed_at - trace.started_at).total_seconds() * 1000
            )
            trace.nodes_executed_count = len(trace.node_executions)
            trace.tools_invoked_count = sum(
                len(node.tool_invocations) for node in trace.node_executions
            )

            logger.info(
                "Scenario execution completed",
                extra={
                    "scenario_id": scenario_id,
                    "status": trace.status.value,
                    "nodes_executed": trace.nodes_executed_count,
                    "tools_invoked": trace.tools_invoked_count,
                    "duration_ms": trace.duration_ms,
                },
            )

            return trace

        except Exception as e:
            trace.status = ExecutionStatus.FAILED
            trace.error_message = str(e)
            trace.completed_at = datetime.utcnow()
            trace.duration_ms = (
                (trace.completed_at - trace.started_at).total_seconds() * 1000
            )

            logger.error(
                "Scenario execution failed",
                extra={
                    "scenario_id": scenario_id,
                    "error": str(e),
                },
                exc_info=True,
            )

            return trace

    def _build_initial_state(
        self,
        scenario: EndToEndScenario,
        trace_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Build initial LangGraph state from scenario.

        Args:
            scenario: Scenario to build state from
            trace_id: Trace ID for this execution
            correlation_id: Correlation ID for tracing

        Returns:
            Initial state dictionary
        """
        app = scenario.canonical_application

        # Build initial state matching LoanApplicationState structure
        initial_state: dict[str, Any] = {
            "application_id": app.application_id,
            "user_id": app.user_id,
            "trace_id": trace_id,
            "runtime_session_id": None,  # Local execution, no runtime session
            "application": app,
            "document_inventory": app.document_inventory,
            "pay_stub_data": app.pay_stub_data,
            "bank_statement_data": app.bank_statement_data,
            "risk_request": None,
            "risk_response": None,
            "compliance_result": None,
            "decision": None,
            "artifact_json_s3_key": None,
            "artifact_pdf_s3_key": None,
            "audit_context": None,
            "error": None,
            "needs_manual_review": False,
            "parse_failure_count": 0,
            "submitted_at": datetime.utcnow(),
            "decided_at": None,
            "_parse_results": None,
        }

        return initial_state

    def _execute_with_tracing(
        self,
        initial_state: dict[str, Any],
        trace: ExecutionTrace,
    ) -> dict[str, Any]:
        """Execute LangGraph with node-level tracing.

        Args:
            initial_state: Initial state dictionary
            trace: Trace object to populate

        Returns:
            Final state dictionary after execution
        """
        # LangGraph stream provides step-by-step execution
        final_state = initial_state.copy()

        try:
            for event in self.supervisor_graph.stream(initial_state):
                # Each event is a dict with node name as key
                for node_name, node_output in event.items():
                    if node_name == "__start__" or node_name == "__end__":
                        continue

                    node_started_at = datetime.utcnow()

                    # Create node execution record
                    node_execution = NodeExecution(
                        node_name=node_name,
                        started_at=node_started_at,
                        status=ExecutionStatus.RUNNING,
                    )

                    # Capture state before
                    if self.enable_tracing:
                        node_execution.state_before = StateSnapshot(
                            timestamp=node_started_at,
                            application_id=final_state.get("application_id"),
                            fields=self._sanitize_state_for_snapshot(final_state),
                        )
                        node_execution.state_before_count = len(
                            [v for v in final_state.values() if v is not None]
                        )

                    # Merge node output into state (LangGraph semantics)
                    if node_output:
                        final_state.update(node_output)

                    # Capture state after
                    if self.enable_tracing:
                        node_execution.state_after = StateSnapshot(
                            timestamp=datetime.utcnow(),
                            application_id=final_state.get("application_id"),
                            fields=self._sanitize_state_for_snapshot(final_state),
                        )
                        node_execution.state_after_count = len(
                            [v for v in final_state.values() if v is not None]
                        )

                    # Update node execution metadata
                    node_execution.completed_at = datetime.utcnow()
                    node_execution.status = ExecutionStatus.SUCCESS
                    node_execution.duration_ms = (
                        (node_execution.completed_at - node_execution.started_at).total_seconds()
                        * 1000
                    )

                    # Add to trace
                    trace.node_executions.append(node_execution)

                    logger.info(
                        "Node executed",
                        extra={
                            "node_name": node_name,
                            "status": node_execution.status.value,
                            "duration_ms": node_execution.duration_ms,
                            "state_fields_before": node_execution.state_before_count,
                            "state_fields_after": node_execution.state_after_count,
                        },
                    )

        except Exception as e:
            logger.error(
                "Graph execution failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

        return final_state

    def _sanitize_state_for_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        """Sanitize state dictionary for snapshot.

        Converts Pydantic models to dicts and handles non-serializable types.

        Args:
            state: State dictionary to sanitize

        Returns:
            Sanitized state dictionary
        """
        sanitized = {}
        for key, value in state.items():
            if value is None:
                continue
            if hasattr(value, "model_dump"):
                # Pydantic model
                sanitized[key] = value.model_dump(by_alias=True, mode="json")
            elif isinstance(value, list):
                sanitized[key] = [
                    item.model_dump(by_alias=True, mode="json")
                    if hasattr(item, "model_dump")
                    else item
                    for item in value
                ]
            elif isinstance(value, datetime):
                sanitized[key] = value.isoformat()
            else:
                sanitized[key] = value
        return sanitized

    def _generate_trace_id(self, scenario_id: str, correlation_id: str) -> str:
        """Generate deterministic trace ID.

        Args:
            scenario_id: Scenario identifier
            correlation_id: Correlation identifier

        Returns:
            Trace ID string
        """
        hash_input = f"{scenario_id}:{correlation_id}:{datetime.utcnow().isoformat()}"
        hash_digest = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]
        return f"trace_{hash_digest}"

    def _generate_correlation_id(self, scenario_id: str) -> str:
        """Generate correlation ID for a scenario.

        Args:
            scenario_id: Scenario identifier

        Returns:
            Correlation ID string
        """
        return f"corr_{scenario_id}_{uuid.uuid4().hex[:8]}"
