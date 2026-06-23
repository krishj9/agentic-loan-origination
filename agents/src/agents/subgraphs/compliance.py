"""Compliance specialist subgraph (P3-T6).

Implements the single-node compliance evaluation pipeline described in
design §5.3 / §8:

    evaluate_compliance

The node collects required inputs from state, calls
``compliance_engine.evaluate``, and stores the structured
``ComplianceResult`` (pass/fail + flags + recommended action) back into state.

All compliance logic is deterministic and externalized to
``agents.tools.compliance_tool`` (and in Phase 4 to config/compliance_rules.yaml)
so no business rules live inside this subgraph.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.log import get_logger
from agents.state import LoanApplicationState
from agents.tools.compliance_tool import ComplianceToolRequest, call_compliance_engine

log = get_logger(__name__)


# ── Node: evaluate_compliance ────────────────────────────────────────────────

def evaluate_compliance(state: LoanApplicationState) -> dict[str, Any]:
    """Run compliance checks and store the structured result in state.

    Inputs are derived from state fields populated by earlier subgraphs:
    * ``risk_response.risk_profile``       — from the risk subgraph
    * ``application.annual_income``        — from intake
    * ``application.requested_loan_amount`` — from intake
    * ``document_inventory``               — for document-completeness check
    """
    application_id = state.get("application_id", "unknown")
    application = state.get("application")
    risk_response = state.get("risk_response")
    inventory = state.get("document_inventory", [])

    if application is None or risk_response is None:
        log.warning(
            "compliance_subgraph.evaluate_compliance.missing_inputs",
            extra={
                "application_id": application_id,
                "has_application": application is not None,
                "has_risk_response": risk_response is not None,
            },
        )
        # Return minimal DECLINE result to surface the data-integrity failure
        from shared.schemas import ComplianceAction, ComplianceFlag, ComplianceResult, ComplianceSeverity

        result = ComplianceResult(
            application_id=application_id,
            passed=False,
            flags=[
                ComplianceFlag(
                    rule_id="MISSING_INPUTS",
                    description="Required application or risk-response data was not available for compliance checks.",
                    severity=ComplianceSeverity.CRITICAL,
                    triggered=True,
                )
            ],
            recommended_action=ComplianceAction.DECLINE,
        )
        return {"compliance_result": result}

    doc_types_present = [doc.document_type.value for doc in inventory if doc.parse_status == "COMPLETED"]

    request = ComplianceToolRequest(
        application_id=application_id,
        annual_income=application.annual_income,
        requested_loan_amount=application.requested_loan_amount,
        risk_profile=risk_response.risk_profile,
        document_types_present=doc_types_present,
        applicant_name=application.applicant_name,
    )
    result = call_compliance_engine(request)

    triggered_rules = [f.rule_id for f in result.flags if f.triggered]
    log.info(
        "compliance_subgraph.evaluate_compliance.complete",
        extra={
            "application_id": application_id,
            "passed": result.passed,
            "recommended_action": result.recommended_action,
            "triggered_rules": triggered_rules,
            "trace_id": state.get("trace_id"),
        },
    )
    return {"compliance_result": result}


# ── Subgraph factory ────────────────────────────────────────────────────────

def build_compliance_subgraph() -> CompiledStateGraph:
    """Compile and return the compliance-evaluation LangGraph subgraph."""

    graph: StateGraph = StateGraph(LoanApplicationState)
    graph.add_node("evaluate_compliance", evaluate_compliance)

    graph.add_edge(START, "evaluate_compliance")
    graph.add_edge("evaluate_compliance", END)

    return graph.compile()
