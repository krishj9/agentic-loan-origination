"""Structured JSON logger for all Phase 4 tool implementations.

Every log record is a JSON object written to stdout so CloudWatch can index
and correlate records by application_id, trace_id, and tool_name per design §10.1.

Usage::

    from tools.log import get_logger

    log = get_logger("risk_engine")
    log.info("evaluation complete", correlation=ctx, risk_profile="PRIME")
"""

import json
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogger:
    """Emits structured JSON log records with mandatory correlation envelope."""

    def __init__(self, tool_name: str) -> None:
        self._tool_name = tool_name

    def _emit(
        self,
        level: str,
        message: str,
        correlation: dict[str, str | None] | None = None,
        **extra: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "tool_name": self._tool_name,
            "message": message,
        }
        if correlation:
            payload.update({k: v for k, v in correlation.items() if v is not None})
        payload.update(extra)
        print(json.dumps(payload, default=str), file=sys.stdout, flush=True)

    def debug(
        self,
        message: str,
        correlation: dict[str, str | None] | None = None,
        **extra: Any,
    ) -> None:
        """Emit a DEBUG-level structured log record."""
        self._emit("DEBUG", message, correlation, **extra)

    def info(
        self,
        message: str,
        correlation: dict[str, str | None] | None = None,
        **extra: Any,
    ) -> None:
        """Emit an INFO-level structured log record."""
        self._emit("INFO", message, correlation, **extra)

    def warning(
        self,
        message: str,
        correlation: dict[str, str | None] | None = None,
        **extra: Any,
    ) -> None:
        """Emit a WARNING-level structured log record."""
        self._emit("WARNING", message, correlation, **extra)

    def error(
        self,
        message: str,
        exc: BaseException | None = None,
        correlation: dict[str, str | None] | None = None,
        **extra: Any,
    ) -> None:
        """Emit an ERROR-level structured log record.

        Pass ``exc`` only for unexpected errors where the stack trace adds value.
        For expected/handled conditions, omit ``exc`` and log as a warning.
        """
        if exc is not None:
            extra["error_type"] = type(exc).__name__
            extra["error_detail"] = str(exc)
        self._emit("ERROR", message, correlation, **extra)


def get_logger(tool_name: str) -> StructuredLogger:
    """Return a structured logger bound to ``tool_name``.

    Args:
        tool_name: Short label included in every log record (e.g. ``"risk_engine"``).

    Returns:
        A :class:`StructuredLogger` instance for the given tool.
    """
    return StructuredLogger(tool_name)
