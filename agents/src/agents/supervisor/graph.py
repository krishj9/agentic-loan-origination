"""Supervisor LangGraph state-machine assembly (P3-T2, P3-T3).

Compiles the 8-node supervisor graph with all conditional and fallback
branches described in design §5.1 and the implementation plan P3-T3.

Node sequence:
    START
      └─ ingest_application
           └─ validate_inputs ──[conditional]──┐
                                               ├── VALID       → process_documents
                                               └── INVALID     → error_terminal → END

              process_documents ──[conditional]──┐
                                                 ├── PARSE_OK  → run_risk
                                                 └── PARSE_FAIL→ make_decision → …

                  run_risk ──[conditional]──┐
                                           ├── NORMAL      → run_compliance → make_decision
                                           └── EARLY_DECLINE→ make_decision → …

                      make_decision ──[conditional]──┐
                                                     ├── REFER   → manual_review_terminal → END
                                                     └── APPROVE/DECLINE → package_artifacts

                          package_artifacts
                               └─ persist_and_publish → END

Routing functions are pure functions that inspect state and return string
labels — they contain no business logic beyond reading a single state field.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from shared.schemas import DecisionOutcome, RiskFlag, RiskProfile

from agents.state import LoanApplicationState
from agents.supervisor.nodes import (
    error_terminal,
    ingest_application,
    make_decision,
    manual_review_terminal,
    package_artifacts,
    persist_and_publish,
    process_documents,
    run_compliance,
    run_risk,
    validate_inputs,
)

# How many parse failures trigger the refer path instead of retrying
_PARSE_FAIL_REFER_THRESHOLD = 1
# Number of extreme-risk flags that trigger early decline (both HIGH_UTILIZATION + LOW_INCOME)
_EXTREME_SUBPRIME_FLAG_COUNT = 2


# ── Routing functions (deterministic, pure, no side effects) ─────────────────

def _route_after_ingest(state: LoanApplicationState) -> str:
    """Route to validate_inputs unless ingest itself encountered a critical error."""
    if state.get("error"):
        return "error_terminal"
    return "validate_inputs"


def _route_after_validate(state: LoanApplicationState) -> str:
    """Route to process_documents on success; error_terminal on missing docs."""
    if state.get("error"):
        return "error_terminal"
    return "process_documents"


def _route_after_process_documents(state: LoanApplicationState) -> str:
    """Route to run_risk when parsing succeeded; make_decision (REFER) on failure."""
    failure_count = state.get("parse_failure_count", 0)
    if failure_count > _PARSE_FAIL_REFER_THRESHOLD:
        return "make_decision"
    return "run_risk"


def _route_after_run_risk(state: LoanApplicationState) -> str:
    """Route to run_compliance for normal risk; make_decision for extreme SUBPRIME.

    An 'extreme' SUBPRIME is defined as SUBPRIME profile *and* both
    HIGH_UTILIZATION and LOW_INCOME flags present simultaneously — indicating
    a clear early-decline case that skips compliance for efficiency.
    """
    risk_response = state.get("risk_response")
    if risk_response is None:
        return "make_decision"
    if risk_response.risk_profile == RiskProfile.SUBPRIME:
        extreme_flags = {RiskFlag.HIGH_UTILIZATION, RiskFlag.LOW_INCOME}
        if extreme_flags.issubset(set(risk_response.risk_flags)):
            return "make_decision"
    return "run_compliance"


def _route_after_make_decision(state: LoanApplicationState) -> str:
    """Route to manual_review_terminal for REFER; package_artifacts otherwise."""
    decision = state.get("decision")
    if decision and decision.outcome == DecisionOutcome.REFER:
        return "manual_review_terminal"
    return "package_artifacts"


# ── Graph factory ────────────────────────────────────────────────────────────

def build_supervisor_graph() -> CompiledStateGraph:
    """Compile and return the supervisor LangGraph state machine.

    The compiled graph is safe to invoke multiple times (each call creates an
    isolated execution context from the provided initial state dict).

    Returns:
        A compiled ``langgraph.graph.state.CompiledStateGraph`` instance.
    """
    graph: StateGraph = StateGraph(LoanApplicationState)

    # ── Nodes ────────────────────────────────────────────────────────────────
    graph.add_node("ingest_application", ingest_application)
    graph.add_node("validate_inputs", validate_inputs)
    graph.add_node("process_documents", process_documents)
    graph.add_node("run_risk", run_risk)
    graph.add_node("run_compliance", run_compliance)
    graph.add_node("make_decision", make_decision)
    graph.add_node("package_artifacts", package_artifacts)
    graph.add_node("persist_and_publish", persist_and_publish)
    graph.add_node("error_terminal", error_terminal)
    graph.add_node("manual_review_terminal", manual_review_terminal)

    # ── Edges ─────────────────────────────────────────────────────────────────
    graph.add_edge(START, "ingest_application")

    graph.add_conditional_edges(
        "ingest_application",
        _route_after_ingest,
        {
            "validate_inputs": "validate_inputs",
            "error_terminal": "error_terminal",
        },
    )
    graph.add_conditional_edges(
        "validate_inputs",
        _route_after_validate,
        {
            "process_documents": "process_documents",
            "error_terminal": "error_terminal",
        },
    )
    graph.add_conditional_edges(
        "process_documents",
        _route_after_process_documents,
        {
            "run_risk": "run_risk",
            "make_decision": "make_decision",
        },
    )
    graph.add_conditional_edges(
        "run_risk",
        _route_after_run_risk,
        {
            "run_compliance": "run_compliance",
            "make_decision": "make_decision",
        },
    )

    graph.add_edge("run_compliance", "make_decision")

    graph.add_conditional_edges(
        "make_decision",
        _route_after_make_decision,
        {
            "package_artifacts": "package_artifacts",
            "manual_review_terminal": "manual_review_terminal",
        },
    )
    graph.add_edge("package_artifacts", "persist_and_publish")

    # Terminal edges → END
    graph.add_edge("persist_and_publish", END)
    graph.add_edge("error_terminal", END)
    graph.add_edge("manual_review_terminal", END)

    return graph.compile()
