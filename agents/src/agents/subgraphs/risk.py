"""Risk specialist subgraph (P3-T5).

Implements the two-node risk evaluation pipeline described in design §5.3 / §7:

    build_risk_request  →  evaluate_risk

* ``build_risk_request`` — maps normalized financial data from state into a
                           canonical ``RiskRequest`` (design §7.2).  Derives
                           ``annual_income`` from the pay-stub when present.
* ``evaluate_risk``      — calls ``risk_engine.evaluate`` and stores the full
                           ``RiskResponse`` (including explainability fields)
                           back into state.

The risk subgraph treats the mock engine as an external provider (design §7.1)
— it has no knowledge of the internal scoring implementation, which lives
entirely in ``agents.tools.risk_engine_tool``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from shared.schemas import RiskRequest

from agents.log import get_logger
from agents.state import LoanApplicationState
from agents.tools.risk_engine_tool import RiskEngineRequest, call_risk_engine

log = get_logger(__name__)

# Annualisation factor used when gross_pay is a monthly figure
_MONTHS_PER_YEAR = 12


# ── Node: build_risk_request ────────────────────────────────────────────────

def build_risk_request(state: LoanApplicationState) -> dict[str, Any]:
    """Construct the canonical ``RiskRequest`` from normalised financial data.

    Income source priority:
    1. ``pay_stub_data.gross_pay * 12``  (derived from monthly pay stub)
    2. ``application.annual_income``      (supplied at submission)

    Utilisation falls back to ``application.debt_utilization`` when no
    bank-statement data is available.
    """
    application_id = state.get("application_id", "unknown")
    application = state.get("application")
    pay_stub = state.get("pay_stub_data")

    # Derive annual income from pay stub gross pay if available
    if pay_stub and pay_stub.gross_pay:
        annual_income = (pay_stub.gross_pay * _MONTHS_PER_YEAR).quantize(Decimal("0.01"))
    elif application:
        annual_income = application.annual_income
    else:
        annual_income = Decimal("0.00")

    debt_utilization = application.debt_utilization if application else Decimal("0.00")

    risk_request = RiskRequest(
        applicant_id=application_id,
        annual_income=annual_income,
        debt_utilization=debt_utilization,
        risk_profile=None,  # Override only via golden-case replay
    )
    log.info(
        "risk_subgraph.build_risk_request",
        extra={
            "application_id": application_id,
            "annual_income": str(annual_income),
            "debt_utilization": str(debt_utilization),
            "trace_id": state.get("trace_id"),
        },
    )
    return {"risk_request": risk_request}


# ── Node: evaluate_risk ──────────────────────────────────────────────────────

def evaluate_risk(state: LoanApplicationState) -> dict[str, Any]:
    """Invoke the risk engine and store the full ``RiskResponse`` in state.

    The engine is treated as an opaque external provider — the node only
    maps between state and the tool contract; no scoring logic lives here.
    """
    application_id = state.get("application_id", "unknown")
    risk_request = state.get("risk_request")

    if risk_request is None:
        log.warning(
            "risk_subgraph.evaluate_risk.missing_request",
            extra={"application_id": application_id},
        )
        return {}

    engine_request = RiskEngineRequest(
        applicant_id=risk_request.applicant_id,
        annual_income=risk_request.annual_income,
        debt_utilization=risk_request.debt_utilization,
        risk_profile=risk_request.risk_profile,
    )
    risk_response = call_risk_engine(engine_request)

    log.info(
        "risk_subgraph.evaluate_risk.complete",
        extra={
            "application_id": application_id,
            "risk_profile": risk_response.risk_profile,
            "credit_score": risk_response.credit_score,
            "flags": [f.value for f in risk_response.risk_flags],
            "trace_id": state.get("trace_id"),
        },
    )
    return {"risk_response": risk_response}


# ── Subgraph factory ────────────────────────────────────────────────────────

def build_risk_subgraph() -> CompiledStateGraph:
    """Compile and return the risk-evaluation LangGraph subgraph."""
    graph: StateGraph = StateGraph(LoanApplicationState)
    graph.add_node("build_risk_request", build_risk_request)
    graph.add_node("evaluate_risk", evaluate_risk)

    graph.add_edge(START, "build_risk_request")
    graph.add_edge("build_risk_request", "evaluate_risk")
    graph.add_edge("evaluate_risk", END)

    return graph.compile()
