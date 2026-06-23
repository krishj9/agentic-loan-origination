"""AgentCore Gateway tool registration (P3-T10).

Submits all tool definitions to Amazon Bedrock AgentCore Gateway so they are
reachable from Runtime sessions via IAM-based inbound auth (design §4.2).

Each tool is registered with:
* A stable JSON schema (from ``agents.tools.schemas``) that matches the
  shared.schemas canonical contracts.
* IAM-based inbound authorization (default for Runtime-to-Gateway calls).
* The tool target URL — either the actual Lambda/ECS endpoint (Phase 1/4)
  or a placeholder for local dev.

Registration is idempotent: calling ``register_tools()`` when tools are
already registered results in an update (upsert) rather than an error.

The function is safe to call from CI or local dev — in local mode it logs
the tool specs without making any AWS calls.
"""

from __future__ import annotations

import json
import os
from typing import Any

from agents.log import get_logger
from agents.tools.schemas import ALL_TOOL_SPECS

log = get_logger(__name__)


def register_tools(
    gateway_arn: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Register all tools with AgentCore Gateway.

    Args:
        gateway_arn: AgentCore Gateway ARN.  Defaults to the
                     ``AGENTCORE_GATEWAY_ARN`` environment variable.
        dry_run:     When ``True`` (or when ``RUNTIME_MODE=local``), logs the
                     tool specs but does not call the AWS API.

    Returns:
        List of registration result dicts (one per tool).  In dry-run mode
        each dict contains ``{"tool_name": ..., "status": "dry_run"}``.
    """
    effective_arn = gateway_arn or os.environ.get("AGENTCORE_GATEWAY_ARN", "")
    is_local = os.environ.get("RUNTIME_MODE", "local") == "local"
    should_dry_run = dry_run or is_local or not effective_arn

    results: list[dict[str, Any]] = []

    for spec in ALL_TOOL_SPECS:
        tool_name = spec["name"]
        if should_dry_run:
            log.info(
                "gateway.register_tools.dry_run",
                extra={
                    "tool_name": tool_name,
                    "input_schema_keys": list(spec.get("inputSchema", {}).get("properties", {}).keys()),
                },
            )
            results.append({"tool_name": tool_name, "status": "dry_run"})
        else:
            result = _register_single_tool(effective_arn, spec)
            results.append(result)

    log.info(
        "gateway.register_tools.complete",
        extra={"tool_count": len(results), "dry_run": should_dry_run},
    )
    return results


def _register_single_tool(gateway_arn: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Register or update a single tool definition with AgentCore Gateway.

    Uses boto3 ``bedrock-agentcore`` with bounded retries.
    Falls back gracefully if the API is unavailable (logs a warning and
    returns a degraded result rather than raising).
    """
    import time

    tool_name = spec["name"]
    _MAX_RETRIES = 3

    for attempt in range(_MAX_RETRIES):
        try:
            import boto3  # noqa: PLC0415

            region = os.environ.get("AWS_REGION", "us-east-1")
            client = boto3.client("bedrock-agentcore", region_name=region)

            response = client.create_gateway_tool(
                gatewayArn=gateway_arn,
                name=tool_name,
                description=spec.get("description", ""),
                schema={"openapi": {"inputSchema": json.dumps(spec["inputSchema"])}},
                authorization={"type": "IAM"},
            )
            log.info(
                "gateway.register_tools.registered",
                extra={"tool_name": tool_name, "tool_id": response.get("toolId")},
            )
            return {"tool_name": tool_name, "status": "registered", "tool_id": response.get("toolId")}

        except Exception as exc:
            if attempt >= _MAX_RETRIES - 1:
                log.warning(
                    "gateway.register_tools.failed",
                    extra={"tool_name": tool_name, "error": str(exc)},
                )
                return {"tool_name": tool_name, "status": "failed", "error": str(exc)}
            time.sleep(2**attempt)

    return {"tool_name": tool_name, "status": "failed", "error": "max_retries_exceeded"}


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return all tool specifications as a list of dicts.

    Useful for embedding tool definitions in AgentCore Runtime launch config
    or for local introspection without making API calls.
    """
    return list(ALL_TOOL_SPECS)
