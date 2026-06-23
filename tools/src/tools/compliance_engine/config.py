"""Compliance rules configuration loader (P4-T5).

Loads and validates ``tools/config/compliance_rules.yaml`` at import time.
Rules are externalized so they can be updated without code changes and verified
directly by the evaluation harness for policy drift (P6-T6).
"""

import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "compliance_rules.yaml"


class RuleConfig(BaseModel):
    """Parsed configuration for a single compliance rule."""

    model_config = ConfigDict(populate_by_name=True)

    rule_id: str
    severity: str
    order: int
    # REQUIRED_DOCUMENT_COMPLETENESS
    required_document_types: list[str] = Field(default_factory=list)
    description_pass: str = ""
    description_template: str = ""
    description: str = ""
    # LOAN_TO_INCOME_RATIO
    max_ratio: Decimal | None = None
    # RISK_BAND_LOAN_CEILING
    ceilings: dict[str, Decimal] = Field(default_factory=dict)


class ActionEscalation(BaseModel):
    """Maps severity labels to recommended compliance actions."""

    model_config = ConfigDict(populate_by_name=True)

    CRITICAL: str = "DECLINE"
    HIGH: str = "DECLINE"
    MEDIUM: str = "REFER"
    LOW: str = "APPROVE"
    NONE: str = "APPROVE"


class CompliancePolicyConfig(BaseModel):
    """Complete parsed compliance policy configuration."""

    model_config = ConfigDict(populate_by_name=True)

    version: str
    rules: dict[str, RuleConfig]
    action_escalation: ActionEscalation
    _ordered_rules: list[RuleConfig] | None = None

    def ordered_rules(self) -> list[RuleConfig]:
        """Return rules sorted by evaluation order."""
        return sorted(self.rules.values(), key=lambda r: r.order)


def _parse_rule(raw: dict[str, Any]) -> RuleConfig:
    ceilings: dict[str, Decimal] = {}
    for band, amount in raw.get("ceilings", {}).items():
        ceilings[band] = Decimal(str(amount))

    return RuleConfig(
        rule_id=raw["rule_id"],
        severity=raw["severity"],
        order=raw["order"],
        required_document_types=raw.get("required_document_types", []),
        description_pass=raw.get("description_pass", ""),
        description_template=raw.get("description_template", ""),
        description=raw.get("description", ""),
        max_ratio=Decimal(str(raw["max_ratio"])) if "max_ratio" in raw else None,
        ceilings=ceilings,
    )


def load_compliance_policy() -> CompliancePolicyConfig:
    """Load and parse the compliance rules YAML configuration.

    Returns:
        Parsed :class:`CompliancePolicyConfig`.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    path_str = os.environ.get("COMPLIANCE_RULES_PATH", "")
    config_path = Path(path_str) if path_str else _DEFAULT_CONFIG_PATH

    with open(config_path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    rules = {name: _parse_rule(rule_raw) for name, rule_raw in raw.get("rules", {}).items()}
    raw_esc = raw.get("action_escalation", {})
    escalation = ActionEscalation(**{k: v for k, v in raw_esc.items() if k in ActionEscalation.model_fields})

    return CompliancePolicyConfig(version=raw.get("version", "1.0"), rules=rules, action_escalation=escalation)


_POLICY: CompliancePolicyConfig | None = None


def get_policy() -> CompliancePolicyConfig:
    """Return the module-level singleton :class:`CompliancePolicyConfig`."""
    global _POLICY  # noqa: PLW0603
    if _POLICY is None:
        _POLICY = load_compliance_policy()
    return _POLICY
