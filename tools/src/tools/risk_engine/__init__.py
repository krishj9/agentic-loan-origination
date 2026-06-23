"""Risk engine package — ``tools.risk_engine.evaluate`` (P4-T3).

Public interface::

    from tools.risk_engine import evaluate
    response = evaluate(request)
"""

from tools.risk_engine.engine import evaluate

__all__ = ["evaluate"]
