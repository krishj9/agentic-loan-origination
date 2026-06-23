"""CLI tool to generate golden-case scenario catalogs.

Implements P6-T3: Generates golden case JSONs for PRIME, NEAR_PRIME, and SUBPRIME
risk profiles with expected outcomes.
"""

import logging
from pathlib import Path

from evaluation.scenarios.generator import ScenarioGenerator
from shared.schemas import DecisionOutcome, RiskProfile

logger = logging.getLogger(__name__)

# Output directory relative to this script
# evaluation/src/evaluation/cli/generate_golden_cases.py -> evaluation/golden
GOLDEN_DIR = Path(__file__).parent.parent.parent.parent / "golden"

def main() -> None:
    """Generate golden-case JSON scenarios."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Generating golden-case catalogs...")

    generator = ScenarioGenerator(base_seed=42)
    
    # Map risk profiles to expected decision outcomes
    # Based on the deterministic mock risk engine and compliance rules
    cases = [
        (RiskProfile.PRIME, DecisionOutcome.APPROVE),
        (RiskProfile.NEAR_PRIME, DecisionOutcome.REFER),
        (RiskProfile.SUBPRIME, DecisionOutcome.DECLINE),
    ]
    
    for profile, expected_outcome in cases:
        scenario_id = f"demo_{profile.value.lower()}"
        
        scenario = generator.generate_end_to_end_scenario(
            scenario_id=scenario_id,
            risk_profile=profile,
            expected_outcome=expected_outcome
        )
        
        output_path = GOLDEN_DIR / f"{profile.value.lower()}_golden.json"
        generator.save_scenario(scenario, output_path)
        logger.info(f"Generated {output_path}")

    logger.info("Golden case generation complete.")

if __name__ == "__main__":
    main()
