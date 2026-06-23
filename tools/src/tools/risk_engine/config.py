"""Risk policy configuration loader (P4-T3).

Loads and validates ``tools/config/risk_policy.yaml`` at import time so the
engine can operate purely from configuration data.  The YAML file is the
single source of truth for band thresholds, score ranges, and flag definitions.
"""

import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

# Default config path — can be overridden via RISK_POLICY_PATH env var
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "risk_policy.yaml"


class ScoreRange(BaseModel):
    """Score range for a risk band."""

    model_config = ConfigDict(populate_by_name=True)

    min: int = Field(description="Inclusive lower bound of the credit score range.")
    max: int = Field(description="Inclusive upper bound of the credit score range.")


class BandConfig(BaseModel):
    """Parsed configuration for a single risk band."""

    model_config = ConfigDict(populate_by_name=True)

    label: str
    description: str
    score_range: ScoreRange
    income_min_exclusive: Decimal | None = None
    utilization_max_exclusive: Decimal | None = None
    income_max_exclusive: Decimal | None = None
    utilization_min_exclusive: Decimal | None = None


class TradelineConfig(BaseModel):
    """Synthetic tradeline generation parameters."""

    model_config = ConfigDict(populate_by_name=True)

    min_count: int = 1
    max_count: int = 5
    account_types: list[str] = Field(default_factory=lambda: ["CREDIT_CARD", "AUTO_LOAN", "MORTGAGE"])
    balance_base: int = 5000
    balance_variance: int = 45000
    utilization_base: float = 0.10
    utilization_variance_pct: int = 60


class RiskPolicyConfig(BaseModel):
    """Complete parsed risk policy configuration."""

    model_config = ConfigDict(populate_by_name=True)

    version: str
    bands: dict[str, BandConfig]
    flags: dict[str, Any]
    tradelines: TradelineConfig


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def _parse_band(name: str, raw: dict[str, Any]) -> BandConfig:
    score = ScoreRange(**raw["score_range"])
    return BandConfig(
        label=raw["label"],
        description=raw["description"],
        score_range=score,
        income_min_exclusive=Decimal(str(raw["income_min_exclusive"])) if "income_min_exclusive" in raw else None,
        utilization_max_exclusive=(
            Decimal(str(raw["utilization_max_exclusive"])) if "utilization_max_exclusive" in raw else None
        ),
        income_max_exclusive=Decimal(str(raw["income_max_exclusive"])) if "income_max_exclusive" in raw else None,
        utilization_min_exclusive=(
            Decimal(str(raw["utilization_min_exclusive"])) if "utilization_min_exclusive" in raw else None
        ),
    )


def load_risk_policy() -> RiskPolicyConfig:
    """Load and parse the risk policy YAML configuration.

    The file path is resolved from the ``RISK_POLICY_PATH`` environment variable,
    falling back to the default ``tools/config/risk_policy.yaml``.

    Returns:
        Parsed :class:`RiskPolicyConfig`.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    path_str = os.environ.get("RISK_POLICY_PATH", "")
    config_path = Path(path_str) if path_str else _DEFAULT_CONFIG_PATH

    raw = _load_yaml(config_path)
    bands = {name: _parse_band(name, band_raw) for name, band_raw in raw.get("bands", {}).items()}
    tradelines = TradelineConfig(**raw.get("tradelines", {}))
    return RiskPolicyConfig(
        version=raw.get("version", "1.0"),
        bands=bands,
        flags=raw.get("flags", {}),
        tradelines=tradelines,
    )


# Module-level singleton — loaded once per process
_POLICY: RiskPolicyConfig | None = None


def get_policy() -> RiskPolicyConfig:
    """Return the module-level singleton :class:`RiskPolicyConfig`.

    Thread-safe for read access (Python GIL guarantees atomicity of the
    assignment for CPython; tests can reload by clearing ``_POLICY``).
    """
    global _POLICY  # noqa: PLW0603
    if _POLICY is None:
        _POLICY = load_risk_policy()
    return _POLICY
