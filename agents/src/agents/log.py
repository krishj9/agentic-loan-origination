"""Structured JSON logging for the agents layer.

Every log record emitted from agent code includes correlation identifiers
so a single application's journey is reconstructable in CloudWatch (design §10.1):
    application_id · user_id · runtime_session_id · trace_id · tool_name (optional)

No secrets or PII are ever logged (org security rule).  Pass only opaque
identifiers as structured context.

Usage::

    from agents.log import get_logger

    log = get_logger(__name__)

    log.info(
        "node.started",
        extra={
            "application_id": state["application_id"],
            "trace_id": state.get("trace_id"),
            "node": "ingest_application",
        },
    )
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any


class _StructuredJSONFormatter(logging.Formatter):
    """Formats every log record as a single-line JSON object.

    Standard LogRecord attributes that are redundant in a JSON payload are
    excluded; all ``extra`` keys passed by the caller are promoted to the
    top-level JSON object for easy CloudWatch filtering.
    """

    _SKIP_KEYS: frozenset[str] = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._SKIP_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured with structured JSON output.

    The log level is read from the ``LOG_LEVEL`` environment variable
    (default: ``INFO``).  A new handler is attached only if the logger has
    none, so calling this multiple times for the same name is idempotent.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_StructuredJSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    return logger
