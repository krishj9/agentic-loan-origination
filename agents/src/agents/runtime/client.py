"""AgentCore Runtime client wrapper (P3-T9).

Implements the session-orchestration interface that the backend's
``RuntimeClient`` (Phase 2, P2-T7) calls to run the LangGraph supervisor:

    create_session(application_id, initial_state) → session_id
    send_event(session_id, event_payload)
    poll_status(session_id) → SessionStatus
    retrieve_result(session_id) → SessionResult

Two operating modes are controlled by the ``RUNTIME_MODE`` environment variable:

* ``"local"``      — invokes the compiled supervisor graph in-process (default
                     for development / CI / local testing, no AWS required).
* ``"agentcore"``  — routes sessions through Amazon Bedrock AgentCore Runtime
                     via boto3.  Requires ``AGENTCORE_RUNTIME_ARN`` to be set.

All outbound calls include timeouts and bounded retries (org comms rule).
Correlation IDs (``application_id``, ``trace_id``, ``runtime_session_id``) are
propagated in every log entry and in the returned ``SessionResult``.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from agents.log import get_logger

log = get_logger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 300
_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_ATTEMPTS = 60  # 300 s total at 5 s interval
_MAX_RETRIES = 3


class RuntimeMode(StrEnum):
    LOCAL = "local"
    AGENTCORE = "agentcore"


@dataclass
class SessionResult:
    """Outcome of a completed AgentCore Runtime (or local) session."""

    session_id: str
    application_id: str
    final_state: dict[str, Any]
    succeeded: bool
    error: str | None = None
    trace_id: str | None = None
    runtime_session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentCoreRuntimeClient:
    """Unified interface for AgentCore Runtime and local in-process execution.

    Instantiate once per process; each ``run_session`` call is stateless.

    Args:
        mode: ``RuntimeMode.LOCAL`` or ``RuntimeMode.AGENTCORE``.
              Defaults to the ``RUNTIME_MODE`` env var (``"local"``).
        runtime_arn: AgentCore Runtime ARN.  Required only in AGENTCORE mode.
        region: AWS region.  Defaults to ``AWS_REGION`` env var or ``"us-east-1"``.
    """

    def __init__(
        self,
        mode: RuntimeMode | None = None,
        runtime_arn: str | None = None,
        region: str | None = None,
    ) -> None:
        self._mode = mode or RuntimeMode(os.environ.get("RUNTIME_MODE", "local"))
        self._runtime_arn = runtime_arn or os.environ.get("AGENTCORE_RUNTIME_ARN", "")
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._boto_client: Any = None  # Lazy-initialised in AGENTCORE mode

    # ── Public interface ─────────────────────────────────────────────────────

    def run_session(
        self,
        application_id: str,
        initial_state: dict[str, Any],
        trace_id: str | None = None,
    ) -> SessionResult:
        """Execute the supervisor graph for the given application.

        In LOCAL mode the graph runs synchronously in-process.
        In AGENTCORE mode the call creates a Runtime session, polls for
        completion, and retrieves the final state.

        Args:
            application_id: Unique application identifier.
            initial_state:  Initial ``LoanApplicationState`` dict populated
                            by the backend submission handler.
            trace_id:       Distributed trace ID propagated from the caller.

        Returns:
            ``SessionResult`` with the final pipeline state and outcome.
        """
        session_id = str(uuid.uuid4())
        state = dict(initial_state)
        state.setdefault("application_id", application_id)
        state.setdefault("trace_id", trace_id or session_id)

        # Explicit trace_id parameter always overrides whatever is in initial_state
        if trace_id:
            state["trace_id"] = trace_id

        log.info(
            "runtime_client.run_session.start",
            extra={
                "application_id": application_id,
                "session_id": session_id,
                "mode": self._mode,
                "trace_id": state.get("trace_id"),
            },
        )
        if self._mode == RuntimeMode.LOCAL:
            return self._run_local(session_id, application_id, state)
        return self._run_agentcore(session_id, application_id, state)

    # ── Local execution ──────────────────────────────────────────────────────

    def _run_local(
        self,
        session_id: str,
        application_id: str,
        initial_state: dict[str, Any],
    ) -> SessionResult:
        """Invoke the compiled supervisor graph in-process."""
        from agents.supervisor.graph import build_supervisor_graph

        supervisor = build_supervisor_graph()
        initial_state["runtime_session_id"] = session_id

        try:
            final_state: dict[str, Any] = supervisor.invoke(initial_state)
            decision = final_state.get("decision")
            outcome = decision.get("outcome") if isinstance(decision, dict) else getattr(decision, "outcome", None)
            log.info(
                "runtime_client.run_session.local.complete",
                extra={
                    "application_id": application_id,
                    "session_id": session_id,
                    "outcome": outcome,
                    "trace_id": initial_state.get("trace_id"),
                },
            )
            return SessionResult(
                session_id=session_id,
                application_id=application_id,
                final_state=final_state,
                succeeded=True,
                trace_id=initial_state.get("trace_id"),
                runtime_session_id=session_id,
            )
        except Exception as exc:
            log.warning(
                "runtime_client.run_session.local.error",
                extra={
                    "application_id": application_id,
                    "session_id": session_id,
                    "error": str(exc),
                },
                exc_info=exc,
            )
            return SessionResult(
                session_id=session_id,
                application_id=application_id,
                final_state=initial_state,
                succeeded=False,
                error=str(exc),
                trace_id=initial_state.get("trace_id"),
                runtime_session_id=session_id,
            )

    # ── AgentCore Runtime execution ──────────────────────────────────────────

    def _boto_agentcore(self) -> Any:  # noqa: ANN401 — boto3 clients have no typed stubs
        """Return a lazily-initialised boto3 bedrock-agentcore-runtime client."""
        if self._boto_client is None:
            import boto3  # noqa: PLC0415

            self._boto_client = boto3.client(
                "bedrock-agentcore-runtime",
                region_name=self._region,
            )
        return self._boto_client

    def _run_agentcore(
        self,
        session_id: str,
        application_id: str,
        initial_state: dict[str, Any],
    ) -> SessionResult:
        """Create an AgentCore Runtime session, poll for completion, retrieve result.

        Implements create → send_event → poll → retrieve with bounded retries
        and explicit timeouts (org comms rule).
        """
        import json

        client = self._boto_agentcore()

        # Step 1: Create session
        runtime_session_id = self._create_agentcore_session(client, application_id, session_id)
        initial_state["runtime_session_id"] = runtime_session_id

        # Step 2: Send the initial event with the application state payload
        self._send_agentcore_event(
            client,
            runtime_session_id,
            {"type": "INVOKE", "payload": json.dumps(initial_state, default=str)},
        )

        # Step 3: Poll for completion
        final_raw = self._poll_agentcore_session(client, runtime_session_id, application_id)

        # Step 4: Parse result
        try:
            final_state: dict[str, Any] = json.loads(final_raw) if isinstance(final_raw, str) else final_raw
        except Exception as parse_exc:
            log.warning(
                "runtime_client.agentcore.parse_result_error",
                extra={"application_id": application_id, "error": str(parse_exc)},
            )
            final_state = initial_state

        return SessionResult(
            session_id=session_id,
            application_id=application_id,
            final_state=final_state,
            succeeded=True,
            trace_id=initial_state.get("trace_id"),
            runtime_session_id=runtime_session_id,
            metadata={"agentcore_session_id": runtime_session_id},
        )

    def _create_agentcore_session(
        self,
        client: Any,  # noqa: ANN401
        application_id: str,
        correlation_id: str,
    ) -> str:
        """Create an AgentCore Runtime session with bounded retries."""
        for attempt in range(_MAX_RETRIES):
            try:
                response = client.create_session(
                    agentRuntimeArn=self._runtime_arn,
                    sessionMetadata={"applicationId": application_id, "correlationId": correlation_id},
                )
                session_id: str = response["sessionId"]
                log.info(
                    "runtime_client.agentcore.session_created",
                    extra={
                        "application_id": application_id,
                        "runtime_session_id": session_id,
                    },
                )
                return session_id
            except Exception as exc:
                if attempt >= _MAX_RETRIES - 1:
                    raise
                log.warning(
                    "runtime_client.agentcore.create_session.retry",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                time.sleep(2**attempt)
        raise RuntimeError("Failed to create AgentCore session after retries")  # unreachable

    def _send_agentcore_event(self, client: Any, session_id: str, event: dict[str, Any]) -> None:  # noqa: ANN401
        """Send an invocation event to an AgentCore Runtime session."""
        for attempt in range(_MAX_RETRIES):
            try:
                client.send_session_event(
                    sessionId=session_id,
                    event=event,
                )
                return
            except Exception as exc:
                if attempt >= _MAX_RETRIES - 1:
                    raise
                log.warning(
                    "runtime_client.agentcore.send_event.retry",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                time.sleep(2**attempt)

    def _poll_agentcore_session(
        self,
        client: Any,  # noqa: ANN401
        session_id: str,
        application_id: str,
    ) -> Any:  # noqa: ANN401
        """Poll the AgentCore Runtime session until it reaches a terminal state."""
        for attempt in range(_MAX_POLL_ATTEMPTS):
            try:
                response = client.get_session(sessionId=session_id)
                status = response.get("status", "UNKNOWN")
                if status in ("COMPLETED", "FAILED", "TIMED_OUT"):
                    log.info(
                        "runtime_client.agentcore.session_terminal",
                        extra={
                            "application_id": application_id,
                            "session_id": session_id,
                            "status": status,
                        },
                    )
                    return response.get("result", {})
            except Exception as exc:
                log.warning(
                    "runtime_client.agentcore.poll.error",
                    extra={"attempt": attempt, "error": str(exc)},
                )
            time.sleep(_POLL_INTERVAL_SECONDS)
        raise TimeoutError(
            f"AgentCore session {session_id} did not complete within "
            f"{_MAX_POLL_ATTEMPTS * _POLL_INTERVAL_SECONDS}s"
        )
