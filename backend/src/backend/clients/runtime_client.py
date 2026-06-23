"""AgentCore Runtime client abstraction.

Isolates the backend from AgentCore Runtime API details (design §3.2 /
P2-T7 note: "isolate behind RuntimeClient interface with local fallback").

Two concrete implementations:
  - LocalRuntimeClient  → invokes LangGraph in-process (RUNTIME_MODE=local).
  - AgentCoreRuntimeClient → calls the real Bedrock AgentCore Runtime via
                            boto3 dispatched in a thread executor to remain
                            async-safe.

The factory `make_runtime_client` selects the implementation based on
settings.runtime_mode so callers never import a concrete class directly.

Org comms rule: all outbound calls have timeouts; retries are bounded.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any

from backend.core.settings import Settings

log = logging.getLogger(__name__)


class RuntimeClient(ABC):
    """Abstract interface for triggering an agent runtime session."""

    @abstractmethod
    async def start_session(self, application_payload: dict[str, Any]) -> str:
        """Start a runtime session for the given application payload.

        Args:
            application_payload: Serialised CanonicalApplication dict.

        Returns:
            A non-empty runtime session ID string for correlation logging.
        """


class LocalRuntimeClient(RuntimeClient):
    """In-process stub used when RUNTIME_MODE=local.

    The LangGraph supervisor is invoked directly in Phase 3.  For Phase 2
    this client simply mints a deterministic session ID so the rest of
    the submission flow (status transitions, correlation logging) works
    end-to-end without a cloud dependency.
    """

    async def start_session(self, application_payload: dict[str, Any]) -> str:
        """Simulate a runtime session start and return a local session ID."""
        session_id = f"local-{uuid.uuid4()}"
        log.info(
            "Local runtime session started",
            extra={
                "runtime_session_id": session_id,
                "application_id": application_payload.get("applicationId"),
            },
        )
        return session_id


class AgentCoreRuntimeClient(RuntimeClient):
    """Invokes the Amazon Bedrock AgentCore Runtime API.

    The underlying boto3 `invoke_agent` call is synchronous, so it is
    dispatched to a thread executor to keep the event loop unblocked.
    Timeouts are enforced via the botocore client config.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def start_session(self, application_payload: dict[str, Any]) -> str:
        """Start an AgentCore Runtime session asynchronously.

        Returns:
            The sessionId returned by AgentCore.
        """
        loop = asyncio.get_event_loop()
        session_id = await loop.run_in_executor(
            None,
            self._start_session_sync,
            application_payload,
        )
        return session_id

    def _start_session_sync(self, application_payload: dict[str, Any]) -> str:
        """Blocking AgentCore invocation (executed in thread pool).

        Retries up to settings.runtime_max_retries times on transient
        errors before re-raising, satisfying the org resilience rule.
        """
        import json

        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError

        config = Config(
            connect_timeout=self._settings.runtime_timeout_seconds,
            read_timeout=self._settings.runtime_timeout_seconds,
            retries={"max_attempts": self._settings.runtime_max_retries, "mode": "adaptive"},
        )

        client = boto3.client(
            "bedrock-agentruntime",
            region_name=self._settings.aws_region,
            config=config,
        )

        session_id = str(uuid.uuid4())

        for attempt in range(1, self._settings.runtime_max_retries + 1):
            try:
                response = client.invoke_agent(
                    agentId=self._settings.agentcore_runtime_arn,
                    agentAliasId="TSTALIASID",
                    sessionId=session_id,
                    inputText=json.dumps(application_payload, default=str),
                )
                returned_session_id: str = response.get("sessionId", session_id)
                log.info(
                    "AgentCore session started",
                    extra={
                        "runtime_session_id": returned_session_id,
                        "application_id": application_payload.get("applicationId"),
                        "attempt": attempt,
                    },
                )
                return returned_session_id
            except (BotoCoreError, ClientError) as exc:
                if attempt == self._settings.runtime_max_retries:
                    log.exception("AgentCore session start failed after all retries", exc_info=exc)
                    raise
                log.warning(
                    "AgentCore session start transient error, retrying",
                    extra={"attempt": attempt, "error": str(exc)},
                )

        # Unreachable; satisfies type checker
        return session_id


def make_runtime_client(settings: Settings) -> RuntimeClient:
    """Factory: select the RuntimeClient implementation from settings.runtime_mode."""
    if settings.runtime_mode == "local":
        return LocalRuntimeClient()
    return AgentCoreRuntimeClient(settings)
