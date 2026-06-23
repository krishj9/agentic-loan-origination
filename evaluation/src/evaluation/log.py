"""Structured JSON logging for evaluation harness.

Provides consistent, structured logging with correlation IDs for traceability.
All log entries are JSON-formatted and include context for debugging and analysis.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any

# Context variables for correlation IDs
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
scenario_id_ctx: ContextVar[str | None] = ContextVar("scenario_id", default=None)


class StructuredJSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs log records as single-line JSON objects with:
    - Standard fields: timestamp, level, logger, message
    - Correlation fields: correlation_id, scenario_id (from context)
    - Custom extra fields passed to logger
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string representation of log record
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation IDs from context if available
        correlation_id = correlation_id_ctx.get()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        scenario_id = scenario_id_ctx.get()
        if scenario_id:
            log_data["scenario_id"] = scenario_id

        # Add any extra fields passed to logger
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add source location
        log_data["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that injects correlation context into extra fields.

    Automatically adds correlation_id and scenario_id from context
    to all log entries without requiring explicit passing.
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Process log message and kwargs to inject context.

        Args:
            msg: Log message
            kwargs: Keyword arguments

        Returns:
            Tuple of (message, updated kwargs with context)
        """
        extra = kwargs.get("extra", {})

        # Inject correlation context
        correlation_id = correlation_id_ctx.get()
        if correlation_id:
            extra["correlation_id"] = correlation_id

        scenario_id = scenario_id_ctx.get()
        if scenario_id:
            extra["scenario_id"] = scenario_id

        # Store extra fields for formatter
        if extra:
            # Create a dict to store in the record
            extra_fields = {}
            for key, value in extra.items():
                extra_fields[key] = value
            kwargs["extra"] = {"extra_fields": extra_fields}

        return msg, kwargs


def configure_logging(level: str = "INFO", enable_console: bool = True) -> None:
    """Configure structured JSON logging for evaluation harness.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Whether to enable console output (default: True)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredJSONFormatter())
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> ContextAdapter:
    """Get a context-aware logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        ContextAdapter that automatically includes correlation context
    """
    base_logger = logging.getLogger(name)
    return ContextAdapter(base_logger, {})


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in context for current execution.

    Args:
        correlation_id: Correlation ID to use for subsequent log entries
    """
    correlation_id_ctx.set(correlation_id)


def set_scenario_id(scenario_id: str) -> None:
    """Set scenario ID in context for current execution.

    Args:
        scenario_id: Scenario ID to use for subsequent log entries
    """
    scenario_id_ctx.set(scenario_id)


def clear_context() -> None:
    """Clear all context variables."""
    correlation_id_ctx.set(None)
    scenario_id_ctx.set(None)
