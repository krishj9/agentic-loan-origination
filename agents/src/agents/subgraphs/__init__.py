"""Specialist LangGraph subgraphs (design §5.3).

Each subgraph operates on the shared ``LoanApplicationState`` and is
compiled once at module import time so it can be invoked as a callable
from the supervisor's stage nodes.
"""

from agents.subgraphs.compliance import build_compliance_subgraph
from agents.subgraphs.document import build_document_subgraph
from agents.subgraphs.packaging import build_packaging_subgraph
from agents.subgraphs.risk import build_risk_subgraph

__all__ = [
    "build_document_subgraph",
    "build_risk_subgraph",
    "build_compliance_subgraph",
    "build_packaging_subgraph",
]
