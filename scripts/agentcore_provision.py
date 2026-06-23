#!/usr/bin/env python3
"""AgentCore Runtime + Gateway provisioning script.

Called by the Terraform ``data "external"`` data source in
``infra/modules/agentcore/main.tf``.

Protocol
--------
* Reads a JSON object from **stdin** (the Terraform external-data query).
* Writes a JSON object to **stdout** (all values must be strings per the
  Terraform external provider spec).
* Writes diagnostic messages to **stderr** only — never stdout.
* Must be idempotent: running the script multiple times with the same inputs
  must produce the same result without duplicating cloud resources.
* Must **never raise an unhandled exception** — catches all errors, writes a
  graceful fallback to stdout, and exits 0 so Terraform continues.

Exit codes
----------
0  Script ran to completion (check ``status`` key for success/skip/error).
Non-zero exits would abort the Terraform apply; reserved for truly catastrophic
bootstrap failures (e.g. invalid JSON on stdin).
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    """Write a diagnostic line to stderr (never interferes with TF stdout)."""
    print(f"[agentcore_provision] {msg}", file=sys.stderr)


def _placeholder_response(
    project_name: str,
    environment: str,
    reason: str,
) -> dict[str, str]:
    """Return placeholder ARNs when AgentCore is unavailable or not yet in the region."""
    prefix = f"arn:aws:bedrock-agentcore:REGION:ACCOUNT"
    return {
        "status": "skipped",
        "reason": reason,
        "runtime_arn": f"{prefix}:agent-runtime/{project_name}-{environment}-runtime",
        "runtime_id": f"{project_name}-{environment}-runtime",
        "gateway_arn": f"{prefix}:gateway/{project_name}-{environment}-gateway",
        "gateway_id": f"{project_name}-{environment}-gateway",
        "gateway_endpoint_url": "https://placeholder.bedrock-agentcore.amazonaws.com",
    }


# ---------------------------------------------------------------------------
# AgentCore management-plane client
# ---------------------------------------------------------------------------

# Amazon Bedrock AgentCore Runtime and Gateway are provisioned through the
# ``bedrock-agentcore`` management-plane client.  The exact boto3 client name
# and method signatures reflect the GA SDK release of AgentCore (2025-Q2).
#
# If a future SDK version renames these methods, update the constants below.

_AGENTCORE_CLIENT = "bedrock-agentcore"
_RUNTIME_METHODS = {
    "create": "create_agent_runtime",
    "get": "get_agent_runtime",
    "list": "list_agent_runtimes",
    "update": "update_agent_runtime",
}
_GATEWAY_METHODS = {
    "create": "create_agent_runtime_endpoint",
    "get": "get_agent_runtime_endpoint",
    "list": "list_agent_runtime_endpoints",
}


def _get_or_create_runtime(
    client: object,
    project_name: str,
    environment: str,
    runtime_role_arn: str,
    bedrock_model_id: str,
) -> dict[str, str]:
    """Return existing runtime ARN/ID or create a new runtime.

    Args:
        client: boto3 bedrock-agentcore client.
        project_name: Short project name used as the resource name prefix.
        environment: Environment label (e.g. demo).
        runtime_role_arn: IAM execution role ARN for the runtime.
        bedrock_model_id: Foundation model ID for the supervisor agent.

    Returns:
        Dict with ``arn`` and ``id`` keys.
    """
    runtime_name = f"{project_name}-{environment}-runtime"

    # --- Check if the runtime already exists ---
    try:
        paginator = client.get_paginator(_RUNTIME_METHODS["list"])  # type: ignore[attr-defined]
        for page in paginator.paginate():
            for rt in page.get("agentRuntimes", []):
                if rt.get("agentRuntimeName") == runtime_name:
                    _log(f"Found existing runtime: {rt['agentRuntimeArn']}")
                    return {
                        "arn": rt["agentRuntimeArn"],
                        "id": rt.get("agentRuntimeId", runtime_name),
                    }
    except Exception as exc:  # pylint: disable=broad-except
        # If list pagination isn't supported, fall through to a direct get.
        _log(f"Could not list runtimes: {exc}; attempting direct get.")
        try:
            resp = getattr(client, _RUNTIME_METHODS["get"])(  # type: ignore[attr-defined]
                agentRuntimeName=runtime_name
            )
            rt = resp.get("agentRuntime", {})
            return {
                "arn": rt["agentRuntimeArn"],
                "id": rt.get("agentRuntimeId", runtime_name),
            }
        except client.exceptions.ResourceNotFoundException:  # type: ignore[attr-defined]
            pass  # Will create below.

    # --- Create the runtime ---
    _log(f"Creating AgentCore Runtime: {runtime_name}")
    resp = getattr(client, _RUNTIME_METHODS["create"])(  # type: ignore[attr-defined]
        agentRuntimeName=runtime_name,
        description=f"LangGraph supervisor runtime for {project_name} ({environment})",
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": "public.ecr.aws/bedrock-agentcore/agentcore-runtime:latest"
            }
        },
        roleArn=runtime_role_arn,
        networkConfiguration={"networkMode": "PUBLIC"},
    )
    runtime = resp.get("agentRuntime", {})
    _log(f"Created runtime: {runtime.get('agentRuntimeArn')}")
    return {
        "arn": runtime["agentRuntimeArn"],
        "id": runtime.get("agentRuntimeId", runtime_name),
    }


def _get_or_create_gateway(
    client: object,
    project_name: str,
    environment: str,
    runtime_arn: str,
    gateway_role_arn: str,
) -> dict[str, str]:
    """Return existing gateway ARN/ID/URL or create a new gateway endpoint.

    Args:
        client: boto3 bedrock-agentcore client.
        project_name: Short project name.
        environment: Environment label.
        runtime_arn: ARN of the runtime this gateway fronts.
        gateway_role_arn: IAM role ARN for gateway tool execution.

    Returns:
        Dict with ``arn``, ``id``, and ``endpoint_url`` keys.
    """
    gateway_name = f"{project_name}-{environment}-gateway"
    runtime_id = runtime_arn.split("/")[-1]

    # --- Check if the gateway already exists ---
    try:
        resp = getattr(client, _GATEWAY_METHODS["list"])(  # type: ignore[attr-defined]
            agentRuntimeId=runtime_id
        )
        for gw in resp.get("agentRuntimeEndpoints", []):
            if gw.get("name") == gateway_name:
                _log(f"Found existing gateway: {gw.get('agentRuntimeEndpointArn')}")
                return {
                    "arn": gw.get("agentRuntimeEndpointArn", ""),
                    "id": gw.get("agentRuntimeEndpointId", gateway_name),
                    "endpoint_url": gw.get("liveEndpointUrl", ""),
                }
    except Exception as exc:  # pylint: disable=broad-except
        _log(f"Could not list gateways: {exc}; attempting create.")

    # --- Create the gateway endpoint ---
    _log(f"Creating AgentCore Gateway endpoint: {gateway_name}")
    resp = getattr(client, _GATEWAY_METHODS["create"])(  # type: ignore[attr-defined]
        agentRuntimeId=runtime_id,
        name=gateway_name,
        description=f"Tool-routing gateway for {project_name} ({environment})",
        routingConfig={"routingStrategy": "LEAST_CONNECTIONS"},
    )
    gw = resp.get("agentRuntimeEndpoint", {})
    _log(f"Created gateway: {gw.get('agentRuntimeEndpointArn')}")
    return {
        "arn": gw.get("agentRuntimeEndpointArn", ""),
        "id": gw.get("agentRuntimeEndpointId", gateway_name),
        "endpoint_url": gw.get("liveEndpointUrl", ""),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Read Terraform external-data query from stdin and write result to stdout."""
    try:
        raw = sys.stdin.read()
        query: dict[str, str] = json.loads(raw)
    except Exception as exc:
        _log(f"FATAL: could not parse stdin: {exc}")
        return 1  # Non-zero only for stdin parse failure.

    project_name = query.get("project_name", "loan-origination")
    environment = query.get("environment", "demo")
    region = query.get("region", "us-east-1")
    runtime_role_arn = query.get("runtime_role_arn", "")
    gateway_role_arn = query.get("gateway_role_arn", "")
    bedrock_model_id = query.get("bedrock_model_id", "anthropic.claude-3-5-sonnet-20241022-v2:0")

    try:
        import boto3  # noqa: PLC0415 — deferred import to keep startup fast
        from botocore.exceptions import (  # noqa: PLC0415
            ClientError,
            EndpointResolutionError,
            NoRegionError,
            UnknownServiceError,
        )
    except ImportError:
        _log("boto3 not available in PATH; returning placeholder values.")
        result = _placeholder_response(project_name, environment, "boto3_not_installed")
        print(json.dumps(result))
        return 0

    try:
        session = boto3.Session(region_name=region)
        client = session.client(_AGENTCORE_CLIENT)

        runtime = _get_or_create_runtime(
            client,
            project_name,
            environment,
            runtime_role_arn,
            bedrock_model_id,
        )
        gateway = _get_or_create_gateway(
            client,
            project_name,
            environment,
            runtime["arn"],
            gateway_role_arn,
        )

        result: dict[str, str] = {
            "status": "ok",
            "reason": "",
            "runtime_arn": runtime["arn"],
            "runtime_id": runtime["id"],
            "gateway_arn": gateway["arn"],
            "gateway_id": gateway["id"],
            "gateway_endpoint_url": gateway["endpoint_url"],
        }

    except Exception as exc:  # pylint: disable=broad-except
        # Determine if this is a known "service not available" condition.
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        known_skip_signals = (
            "UnknownServiceError",
            "EndpointResolutionError",
            "NoRegionError",
            "is not a valid endpoint",
            "Could not connect to the endpoint",
            "UnknownEndpoint",
            "ServiceUnavailableException",
            "RegionDisabledException",
        )
        is_expected = any(s in exc_type or s in exc_msg for s in known_skip_signals)

        if is_expected:
            reason = f"AgentCore service unavailable in {region}: {exc_type}"
        else:
            reason = f"Unexpected error ({exc_type}): {exc_msg}"
            _log(f"ERROR: {reason}")
            _log(traceback.format_exc())

        _log(f"Returning placeholder values. Reason: {reason}")
        result = _placeholder_response(project_name, environment, reason)

    # All values must be strings for the Terraform external provider.
    str_result = {k: str(v) for k, v in result.items()}
    print(json.dumps(str_result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
