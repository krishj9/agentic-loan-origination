"""CLI tool to generate synthetic sample PDF fixtures.

Implements P6-T2: Generates PRIME, NEAR_PRIME, and SUBPRIME packs
of synthetic paystubs and bank statements.
"""

import logging
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from evaluation.scenarios.generator import ScenarioGenerator
from shared.schemas import DocumentType, RiskProfile

logger = logging.getLogger(__name__)

# Output directory relative to this script
# evaluation/src/evaluation/cli/generate_fixtures.py -> evaluation/fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"

def generate_pdf(path: Path, lines: list[str]) -> None:
    """Generate a simple PDF with the given text lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()

def main() -> None:
    """Generate synthetic PDF fixtures for all risk profiles."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Generating synthetic PDF fixtures...")

    generator = ScenarioGenerator(base_seed=42)
    profiles = [RiskProfile.PRIME, RiskProfile.NEAR_PRIME, RiskProfile.SUBPRIME]

    for profile in profiles:
        scenario_id = f"demo_{profile.value.lower()}"
        
        # 1. Paystub
        paystub_scenario = generator.generate_document_parsing_scenario(
            scenario_id=scenario_id,
            document_type=DocumentType.PAYSTUB
        )
        paystub_fields = paystub_scenario.expected_fields
        paystub_path = FIXTURES_DIR / profile.value.lower() / f"paystub_{scenario_id}.pdf"
        
        generate_pdf(paystub_path, [
            "PAY STUB",
            f"Employee: {paystub_fields.employee_name}",
            f"Employer: {paystub_fields.employer_name}",
            f"Pay Period: {paystub_fields.pay_period_start} to {paystub_fields.pay_period_end}",
            f"Pay Date: {paystub_fields.pay_date}",
            f"Gross Pay: ${paystub_fields.gross_pay:,.2f}",
            f"Deductions: ${paystub_fields.deductions:,.2f}",
            f"Net Pay: ${paystub_fields.net_pay:,.2f}",
            f"YTD Gross Pay: ${paystub_fields.ytd_gross_pay:,.2f}",
            f"YTD Net Pay: ${paystub_fields.ytd_net_pay:,.2f}",
        ])
        logger.info(f"Generated {paystub_path}")

        # 2. Bank Statement
        stmt_scenario = generator.generate_document_parsing_scenario(
            scenario_id=scenario_id,
            document_type=DocumentType.BANK_STATEMENT
        )
        stmt_fields = stmt_scenario.expected_fields
        stmt_path = FIXTURES_DIR / profile.value.lower() / f"statement_{scenario_id}.pdf"
        
        stmt_lines = [
            "BANK STATEMENT",
            f"Account Holder: {stmt_fields.account_holder_name}",
            f"Account: {stmt_fields.account_number_masked}",
            f"Period: {stmt_fields.statement_period_start} to {stmt_fields.statement_period_end}",
            f"Opening Balance: ${stmt_fields.opening_balance:,.2f}",
            f"Closing Balance: ${stmt_fields.closing_balance:,.2f}",
            "",
            "Transactions:"
        ]
        
        for t in stmt_fields.transactions:
            stmt_lines.append(f"  {t.transaction_date}: {t.description} | ${t.amount:,.2f}")
            
        generate_pdf(stmt_path, stmt_lines)
        logger.info(f"Generated {stmt_path}")

    logger.info("Fixture generation complete.")

if __name__ == "__main__":
    main()
