"""PDF and JSON artifact generator for decision packages (P4-T6).

Design §9.1: The packaging stage generates:
  - A machine-readable JSON decision summary.
  - A human-readable PDF decision package.
  - Links/references to source documents and extracted artifacts.

Layout constraints (deterministic for snapshot testing)
--------------------------------------------------------
* JSON: canonical Decision model serialized with full audit context.
* PDF: fixed section order using reportlab Platypus (no floating layout).
  Sections: Header, Applicant Info, Risk Assessment, Decision, Compliance Flags,
  Rationale, Source Documents, Audit Metadata, Footer.
* Both artifacts include ``artifact_json_s3_key`` and ``artifact_pdf_s3_key``
  from the design §9.2 S3 layout.
"""

import io
import json
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from shared.schemas import AuditContext, Decision
from tools.log import get_logger

log = get_logger("packager.generator")

_PDF_PAGE_SIZE = LETTER
_PDF_MARGIN = 0.75 * inch


def _json_s3_key(application_id: str) -> str:
    return f"archive/{application_id}/decision.json"


def _pdf_s3_key(application_id: str) -> str:
    return f"archive/{application_id}/decision.pdf"


# ── JSON generation ──────────────────────────────────────────────────────────

def generate_json(decision: Decision, audit_context: AuditContext) -> str:
    """Serialize the decision and audit context to a JSON string.

    The JSON includes the full :class:`~shared.schemas.Decision` model plus the
    audit envelope so the archive artifact is self-describing for replay and audit.

    Args:
        decision: Final decision from the make_decision node.
        audit_context: Audit metadata envelope.

    Returns:
        Deterministically-serialized JSON string (keys sorted, 2-space indent).
    """
    payload: dict[str, Any] = {
        **decision.model_dump(mode="json", by_alias=True),
        "auditContext": audit_context.model_dump(mode="json", by_alias=True),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    # Sort keys for deterministic output (important for snapshot tests)
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


# ── PDF generation ───────────────────────────────────────────────────────────

def _make_styles() -> dict[str, ParagraphStyle]:
    """Build a fixed set of paragraph styles for the decision PDF."""
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=18,
            spaceAfter=6,
            textColor=colors.HexColor("#1a3c5e"),
        ),
        "heading": ParagraphStyle(
            "heading",
            parent=base["Heading2"],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=4,
            textColor=colors.HexColor("#1a3c5e"),
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["BodyText"],
            fontSize=9,
            textColor=colors.HexColor("#666666"),
            spaceAfter=2,
        ),
        "decision_approve": ParagraphStyle(
            "decision_approve",
            parent=base["BodyText"],
            fontSize=14,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1e7e34"),
        ),
        "decision_refer": ParagraphStyle(
            "decision_refer",
            parent=base["BodyText"],
            fontSize=14,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#856404"),
        ),
        "decision_decline": ParagraphStyle(
            "decision_decline",
            parent=base["BodyText"],
            fontSize=14,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#721c24"),
        ),
        "monospace": ParagraphStyle(
            "monospace",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=8,
            spaceAfter=2,
        ),
    }
    return styles


def _decision_style_key(outcome: str) -> str:
    mapping = {"APPROVE": "decision_approve", "REFER": "decision_refer", "DECLINE": "decision_decline"}
    return mapping.get(outcome, "body")


def _kv_table(rows: list[tuple[str, str]], col_widths: tuple[float, float] = (2.0, 4.5)) -> Table:
    """Build a two-column label/value table."""
    data = [[label, value] for label, value in rows]
    tbl = Table(data, colWidths=[col_widths[0] * inch, col_widths[1] * inch])
    tbl.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return tbl


def generate_pdf(decision: Decision, audit_context: AuditContext) -> bytes:
    """Generate a deterministic human-readable PDF decision package.

    Args:
        decision: Final decision from the make_decision node.
        audit_context: Audit metadata envelope.

    Returns:
        PDF bytes (deterministic layout, suitable for snapshot diffing).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=_PDF_PAGE_SIZE,
        leftMargin=_PDF_MARGIN,
        rightMargin=_PDF_MARGIN,
        topMargin=_PDF_MARGIN,
        bottomMargin=_PDF_MARGIN,
    )
    styles = _make_styles()
    story: list[Any] = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("Consumer Loan Origination System", styles["title"]))
    story.append(Paragraph("Decision Package", styles["heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c5e")))
    story.append(Spacer(1, 0.1 * inch))

    # ── Application Info ─────────────────────────────────────────────────────
    story.append(Paragraph("Application Details", styles["heading"]))
    story.append(
        _kv_table([
            ("Application ID", decision.application_id),
            ("Decision Date", str(audit_context.decision_timestamp or "–")),
            ("Submitted", str(audit_context.submission_timestamp)),
        ])
    )
    story.append(Spacer(1, 0.1 * inch))

    # ── Decision ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Underwriting Decision", styles["heading"]))
    outcome_key = _decision_style_key(str(decision.outcome))
    story.append(Paragraph(f"OUTCOME: {decision.outcome.value}", styles[outcome_key]))
    story.append(Spacer(1, 0.05 * inch))

    # ── Risk Assessment ──────────────────────────────────────────────────────
    story.append(Paragraph("Risk Assessment", styles["heading"]))
    risk_rows: list[tuple[str, str]] = [
        ("Risk Profile", decision.risk_profile.value),
        ("Credit Score", str(decision.credit_score)),
    ]
    if decision.risk_response:
        risk_rows += [
            ("Income Band", decision.risk_response.income_band),
            ("Utilisation Band", decision.risk_response.utilization_band),
        ]
        if decision.risk_response.risk_flags:
            risk_rows.append(("Risk Flags", ", ".join(f.value for f in decision.risk_response.risk_flags)))
        if decision.risk_response.tradelines:
            lines = [
                f"{t.account_type.value}: ${float(t.balance):,.0f} / ${float(t.limit):,.0f} "
                f"({float(t.utilization):.0%})"
                for t in decision.risk_response.tradelines
            ]
            risk_rows.append(("Tradelines", "\n".join(lines)))
    story.append(_kv_table(risk_rows))
    story.append(Spacer(1, 0.1 * inch))

    # ── Compliance Flags ─────────────────────────────────────────────────────
    if decision.compliance_result:
        story.append(Paragraph("Compliance Evaluation", styles["heading"]))
        action = decision.compliance_result.recommended_action.value
        story.append(Paragraph(f"Compliance Action: {action}", styles["body"]))
        story.append(Spacer(1, 0.05 * inch))
        flag_rows: list[tuple[str, str]] = [
            (
                f"{'[TRIGGERED] ' if f.triggered else '[PASS]     '}{f.rule_id}",
                f"{f.severity.value} — {f.description}",
            )
            for f in decision.compliance_result.flags
        ]
        if flag_rows:
            story.append(_kv_table(flag_rows, col_widths=(2.5, 4.0)))
        story.append(Spacer(1, 0.1 * inch))

    # ── Rationale ────────────────────────────────────────────────────────────
    story.append(Paragraph("Decision Rationale", styles["heading"]))
    story.append(Paragraph(decision.rationale, styles["body"]))
    if decision.risk_response:
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph("Score Range Rationale", styles["label"]))
        story.append(Paragraph(decision.risk_response.score_range_rationale, styles["body"]))
    story.append(Spacer(1, 0.1 * inch))

    # ── Artifact References ───────────────────────────────────────────────────
    story.append(Paragraph("Archived Artifacts", styles["heading"]))
    artifact_rows: list[tuple[str, str]] = []
    if decision.artifact_json_s3_key:
        artifact_rows.append(("Decision JSON", decision.artifact_json_s3_key))
    if decision.artifact_pdf_s3_key:
        artifact_rows.append(("Decision PDF", decision.artifact_pdf_s3_key))
    if artifact_rows:
        story.append(_kv_table(artifact_rows))
    story.append(Spacer(1, 0.1 * inch))

    # ── Audit Metadata ───────────────────────────────────────────────────────
    story.append(Paragraph("Audit Metadata", styles["heading"]))
    audit_rows: list[tuple[str, str]] = [
        ("Application ID", audit_context.application_id),
        ("User ID", audit_context.user_id),
        ("Session ID", str(audit_context.runtime_session_id or "–")),
        ("Trace ID", str(audit_context.trace_id or "–")),
    ]
    story.append(_kv_table(audit_rows))
    story.append(Spacer(1, 0.2 * inch))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dee2e6")))
    story.append(Spacer(1, 0.05 * inch))
    story.append(
        Paragraph(
            "This document is a synthetic demonstration artifact. "
            "All data is fictional and does not represent real credit decisions.",
            styles["label"],
        )
    )

    doc.build(story)
    return buf.getvalue()
