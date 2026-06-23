"""CLI utility for generating evaluation scenarios.

Usage:
    uv run python -m evaluation.cli.generate_scenarios --output-dir ./scenarios --count 10
"""

import argparse
import sys
from pathlib import Path

from shared.schemas import DecisionOutcome, DocumentType, RiskProfile

from evaluation.log import configure_logging, get_logger
from evaluation.scenarios import ScenarioGenerator

logger = get_logger(__name__)


def main() -> int:
    """Main entry point for scenario generation CLI.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="Generate evaluation scenarios for loan origination system")

    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Output directory for generated scenarios (will be created)"
    )
    parser.add_argument("--base-seed", type=int, default=42, help="Base seed for scenario generation (default: 42)")
    parser.add_argument("--count", type=int, default=10, help="Number of scenarios per type to generate (default: 10)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")

    args = parser.parse_args()

    # Configure logging
    configure_logging(level=args.log_level)

    logger.info("Starting scenario generation", extra={"output_dir": str(args.output_dir), "count": args.count})

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize generator
    generator = ScenarioGenerator(base_seed=args.base_seed)

    try:
        # Generate document parsing scenarios
        doc_dir = args.output_dir / "document_parsing"
        doc_dir.mkdir(exist_ok=True)

        for i in range(args.count // 2):
            # Paystub scenarios
            scenario = generator.generate_document_parsing_scenario(
                scenario_id=f"parse_paystub_{i:03d}", document_type=DocumentType.PAYSTUB, seed=args.base_seed + i
            )
            generator.save_scenario(scenario, doc_dir / f"parse_paystub_{i:03d}.json")

            # Bank statement scenarios
            scenario = generator.generate_document_parsing_scenario(
                scenario_id=f"parse_statement_{i:03d}",
                document_type=DocumentType.BANK_STATEMENT,
                seed=args.base_seed + i + 1000,
            )
            generator.save_scenario(scenario, doc_dir / f"parse_statement_{i:03d}.json")

        logger.info("Generated document parsing scenarios", extra={"count": args.count})

        # Generate risk scoring scenarios (distribute across profiles)
        risk_dir = args.output_dir / "risk_scoring"
        risk_dir.mkdir(exist_ok=True)

        risk_profiles = [RiskProfile.PRIME, RiskProfile.NEAR_PRIME, RiskProfile.SUBPRIME]
        for i in range(args.count):
            profile = risk_profiles[i % len(risk_profiles)]
            scenario = generator.generate_risk_scoring_scenario(
                scenario_id=f"risk_{profile.value.lower()}_{i:03d}",
                risk_profile=profile,
                seed=args.base_seed + i + 2000,
            )
            generator.save_scenario(scenario, risk_dir / f"risk_{profile.value.lower()}_{i:03d}.json")

        logger.info("Generated risk scoring scenarios", extra={"count": args.count})

        # Generate compliance scenarios
        compliance_dir = args.output_dir / "compliance"
        compliance_dir.mkdir(exist_ok=True)

        for i in range(args.count):
            trigger_flags = i % 2 == 0  # Alternate between triggering and clean
            scenario = generator.generate_compliance_scenario(
                scenario_id=f"compliance_{i:03d}", seed=args.base_seed + i + 3000, trigger_flags=trigger_flags
            )
            generator.save_scenario(scenario, compliance_dir / f"compliance_{i:03d}.json")

        logger.info("Generated compliance scenarios", extra={"count": args.count})

        # Generate end-to-end scenarios (golden cases)
        e2e_dir = args.output_dir / "end_to_end"
        e2e_dir.mkdir(exist_ok=True)

        e2e_configs = [
            (RiskProfile.PRIME, DecisionOutcome.APPROVE),
            (RiskProfile.NEAR_PRIME, DecisionOutcome.REFER),
            (RiskProfile.SUBPRIME, DecisionOutcome.DECLINE),
        ]

        for i in range(args.count):
            profile, outcome = e2e_configs[i % len(e2e_configs)]
            scenario = generator.generate_end_to_end_scenario(
                scenario_id=f"e2e_{outcome.value.lower()}_{i:03d}",
                risk_profile=profile,
                expected_outcome=outcome,
                seed=args.base_seed + i + 4000,
            )
            generator.save_scenario(scenario, e2e_dir / f"e2e_{outcome.value.lower()}_{i:03d}.json")

        logger.info("Generated end-to-end scenarios", extra={"count": args.count})

        logger.info(
            "Scenario generation complete",
            extra={
                "total_scenarios": args.count * 4 + args.count,  # doc parsing counts as 2 types
                "output_dir": str(args.output_dir),
            },
        )

        return 0

    except Exception as e:
        logger.error("Scenario generation failed", extra={"error": str(e)}, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
