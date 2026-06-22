"""Audit context fields attached to every decision artifact stored in S3.

These fields satisfy the traceability requirements in design §4.4:
  application_id, user_id, submission_timestamp, decision_timestamp,
  runtime_session_id, and trace_id.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditContext(BaseModel):
    """Immutable audit envelope written into every S3 archive artifact.

    All timestamps are UTC ISO-8601 strings to keep JSON artifacts
    self-describing without requiring a timezone-aware consumer.
    """

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(description="Unique identifier for the loan application.")
    user_id: str = Field(description="Cognito sub (user identifier) of the submitting loan officer.")
    submission_timestamp: datetime = Field(description="UTC timestamp when the application was submitted.")
    decision_timestamp: datetime | None = Field(
        default=None,
        description="UTC timestamp when the final decision was produced. Null while processing.",
    )
    runtime_session_id: str | None = Field(
        default=None,
        description="AgentCore Runtime session identifier for cross-log correlation.",
    )
    trace_id: str | None = Field(
        default=None,
        description="Distributed trace ID propagated across all structured log entries.",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "application_id": "app_01J000000000000000000000",
                "user_id": "cognito-sub-abc123",
                "submission_timestamp": "2026-06-22T18:00:00Z",
                "decision_timestamp": "2026-06-22T18:00:45Z",
                "runtime_session_id": "session_xyz789",
                "trace_id": "trace_abc456",
            }
        },
    )
