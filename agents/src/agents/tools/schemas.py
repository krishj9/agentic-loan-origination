"""Stable JSON-schema definitions for every AgentCore Gateway tool (P3-T10).

These dictionaries are the authoritative tool specifications submitted to
AgentCore Gateway via ``agents.runtime.gateway.register_tools()``.  The
``inputSchema`` fields match the Pydantic request models in each tool module;
changes here must be reflected in both the tool implementation and the
shared.schemas package.

Tool names follow the ``<namespace>.<verb>`` convention from design §6.2 / §7.2.
"""

from __future__ import annotations

from typing import Any

# ── llamaparse.parse_financial_pdf ─────────────────────────────────────────
LLAMAPARSE_TOOL_SPEC: dict[str, Any] = {
    "name": "llamaparse.parse_financial_pdf",
    "description": (
        "Upload a financial PDF from S3, run it through LlamaParse with "
        "document-type-specific parsing instructions, and return structured "
        "field extraction alongside raw markdown and confidence notes."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "Unique application identifier for correlation.",
            },
            "document_id": {
                "type": "string",
                "description": "Unique document identifier within the application.",
            },
            "document_type": {
                "type": "string",
                "enum": ["PAYSTUB", "BANK_STATEMENT", "ID", "OTHER"],
                "description": "Document class — drives the parse profile.",
            },
            "s3_key": {
                "type": "string",
                "description": "Full S3 object key under the incoming/ prefix.",
            },
            "parse_profile": {
                "type": "string",
                "description": "Named parse profile (e.g. 'paystub_v1', 'bank_statement_v1').",
            },
        },
        "required": ["application_id", "document_id", "document_type", "s3_key"],
    },
}

# ── risk_engine.evaluate ────────────────────────────────────────────────────
RISK_ENGINE_TOOL_SPEC: dict[str, Any] = {
    "name": "risk_engine.evaluate",
    "description": (
        "Run the deterministic mock risk engine for a given applicant.  "
        "Returns a risk profile (PRIME / NEAR_PRIME / SUBPRIME), synthetic "
        "credit score, tradelines, risk flags, and explainability fields.  "
        "The optional risk_profile override pins the band for golden-case tests."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "applicant_id": {
                "type": "string",
                "description": "Application/applicant identifier (seeds tradeline generation).",
            },
            "annual_income": {
                "type": "number",
                "description": "Annualised gross income in USD.",
            },
            "debt_utilization": {
                "type": "number",
                "description": "Aggregate debt utilisation ratio (0.0–1.0).",
            },
            "risk_profile": {
                "type": "string",
                "enum": ["PRIME", "NEAR_PRIME", "SUBPRIME"],
                "description": "Optional override for golden-case replay tests.",
            },
        },
        "required": ["applicant_id", "annual_income", "debt_utilization"],
    },
}

# ── compliance_engine.evaluate ──────────────────────────────────────────────
COMPLIANCE_ENGINE_TOOL_SPEC: dict[str, Any] = {
    "name": "compliance_engine.evaluate",
    "description": (
        "Run rule-based compliance checks against the application.  "
        "Returns structured pass/fail flags with severity levels and a "
        "recommended action (APPROVE / REFER / DECLINE)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "Application identifier.",
            },
            "annual_income": {
                "type": "number",
                "description": "Annualised gross income in USD.",
            },
            "requested_loan_amount": {
                "type": "number",
                "description": "Requested loan amount in USD.",
            },
            "risk_profile": {
                "type": "string",
                "enum": ["PRIME", "NEAR_PRIME", "SUBPRIME"],
                "description": "Risk band from the risk engine.",
            },
            "document_types_present": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of document type strings that have been successfully parsed.",
            },
            "applicant_name": {
                "type": "string",
                "description": "Applicant full name (used for duplicate-detection checks).",
            },
        },
        "required": [
            "application_id",
            "annual_income",
            "requested_loan_amount",
            "risk_profile",
            "document_types_present",
        ],
    },
}

# ── packaging.generate_artifacts ────────────────────────────────────────────
PACKAGING_TOOL_SPEC: dict[str, Any] = {
    "name": "packaging.generate_artifacts",
    "description": (
        "Generate a machine-readable decision JSON summary and a human-readable "
        "PDF, then write both to archive/{application_id}/ in S3 with full "
        "audit metadata.  Returns the S3 keys for both artifacts."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "Application identifier used to derive the S3 prefix.",
            },
            "decision": {
                "type": "object",
                "description": "Serialised Decision object from the make_decision node.",
            },
            "audit_context": {
                "type": "object",
                "description": "Serialised AuditContext to embed in the artifacts.",
            },
            "s3_bucket": {
                "type": "string",
                "description": "Target S3 bucket name.",
            },
        },
        "required": ["application_id", "decision", "audit_context", "s3_bucket"],
    },
}

# ── Registry of all tool specs (used by gateway.register_tools()) ────────────
ALL_TOOL_SPECS: list[dict[str, Any]] = [
    LLAMAPARSE_TOOL_SPEC,
    RISK_ENGINE_TOOL_SPEC,
    COMPLIANCE_ENGINE_TOOL_SPEC,
    PACKAGING_TOOL_SPEC,
]
