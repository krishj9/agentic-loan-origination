"""Structured JSON logging and per-request correlation-ID middleware.

Every log line emitted by the backend is a JSON object that includes:
  - timestamp, level, logger, message
  - trace_id  (injected by CorrelationMiddleware from X-Trace-Id header)
  - application_id  (set via set_application_id() in service layer)
  - user_id         (set via set_user_id() in auth layer)
  - any extra fields passed as keyword arguments to the logger

Design §10.1: all components share these IDs for CloudWatch correlation.
"""

import json
import logging
import sys
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── Per-request context variables ─────────────────────────────────────────────
_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
_application_id_var: ContextVar[str | None] = ContextVar("application_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_trace_id() -> str | None:
    """Return the trace ID for the current async context."""
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Bind a trace ID to the current async context."""
    _trace_id_var.set(trace_id)


def get_application_id() -> str | None:
    """Return the application ID for the current async context."""
    return _application_id_var.get()


def set_application_id(application_id: str) -> None:
    """Bind an application ID to the current async context."""
    _application_id_var.set(application_id)


def get_user_id() -> str | None:
    """Return the user ID for the current async context."""
    return _user_id_var.get()


def set_user_id(user_id: str) -> None:
    """Bind a user ID to the current async context."""
    _user_id_var.set(user_id)


# ── Formatter ─────────────────────────────────────────────────────────────────

_EXCLUDED_LOG_RECORD_KEYS = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "id",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class StructuredJSONFormatter(logging.Formatter):
    """Formats every log record as a single JSON line.

    Extra fields passed via the `extra={}` kwarg are merged at the top
    level of the JSON object — keep names collision-free with the
    standard fields (timestamp, level, logger, message, trace_id…).
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a LogRecord to a compact JSON string."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject correlation IDs from async context variables
        trace_id = _trace_id_var.get()
        if trace_id:
            entry["trace_id"] = trace_id

        application_id = _application_id_var.get()
        if application_id:
            entry["application_id"] = application_id

        user_id = _user_id_var.get()
        if user_id:
            entry["user_id"] = user_id

        # Merge caller-supplied extra fields
        for key, value in record.__dict__.items():
            if key not in _EXCLUDED_LOG_RECORD_KEYS and not key.startswith("_"):
                entry[key] = value

        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


# ── Configuration ─────────────────────────────────────────────────────────────


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger to emit structured JSON on stdout.

    Should be called once at application startup before any log records
    are produced.  Subsequent calls are idempotent.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Silence noisy third-party loggers that would drown application logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("aioboto3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Middleware ─────────────────────────────────────────────────────────────────


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Injects a trace ID into the async context for every incoming request.

    Reads X-Trace-Id from the request header if present; otherwise generates
    a new UUID.  Echoes the value back in the response header so callers can
    correlate client-side and server-side logs.
    """

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        """Extract or create a trace ID and bind it for the request lifetime."""
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        set_trace_id(trace_id)

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
