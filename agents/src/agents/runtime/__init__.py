"""AgentCore Runtime client and Gateway registration (P3-T9, P3-T10).

``AgentCoreRuntimeClient`` — wraps boto3 calls to Amazon Bedrock AgentCore
Runtime for session creation, event submission, status polling, and artifact
retrieval.  Supports a local fallback mode that runs the LangGraph supervisor
in-process (``RUNTIME_MODE=local`` env var).

``register_tools`` — submits tool definitions to AgentCore Gateway so they
are reachable from Runtime sessions via IAM-based inbound auth (design §4.2).
"""

from agents.runtime.client import AgentCoreRuntimeClient, RuntimeMode, SessionResult
from agents.runtime.gateway import register_tools

__all__ = [
    "AgentCoreRuntimeClient",
    "RuntimeMode",
    "SessionResult",
    "register_tools",
]
