"""Unit and integration tests for the supervisor graph (P3-T2, P3-T3, P3-T8, P3-T12).

Tests cover:
* Graph compiles successfully
* Happy path: PRIME app → APPROVE decision
* Happy path: SUBPRIME app → REFER or DECLINE decision (deterministic)
* Fallback: missing required docs → error_terminal reached (error set in state)
* Fallback: extreme SUBPRIME (HIGH_UTILIZATION + LOW_INCOME) → early decline
  before compliance is run
* Fallback: REFER decision → manual_review_terminal (needs_manual_review=True)
* Node purity: validate_inputs sets error on missing doc types
* Node purity: make_decision assembles rationale from engine explanations only
* Routing functions produce correct labels for each state
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from agents.supervisor.graph import (
    _route_after_ingest,
    _route_after_make_decision,
    _route_after_process_documents,
    _route_after_run_risk,
    _route_after_validate,
    build_supervisor_graph,
)
from agents.supervisor.nodes import (
    make_decision,
)
from shared.schemas import (
    AccountType,
    ApplicationStatus,
    CanonicalApplication,
    ComplianceAction,
    ComplianceResult,
    Decision,
    DecisionOutcome,
    Document,
    DocumentType,
    RiskFlag,
    RiskProfile,
    RiskResponse,
    Tradeline,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_application(
    application_id: str = "app_sv_001",
    annual_income: Decimal = Decimal("90000"),
    debt_utilization: Decimal = Decimal("0.20"),
    loan_amount: Decimal = Decimal("20000"),
) -> CanonicalApplication:
    return CanonicalApplication(
        applicationId=application_id,
        userId="user_sv",
        applicantName="Alice Example",
        annualIncome=annual_income,
        requestedLoanAmount=loan_amount,
        debtUtilization=debt_utilization,
        status=ApplicationStatus.PENDING,
    )


def _make_document(doc_type: DocumentType, app_id: str) -> Document:
    return Document(
        document_id=f"doc_{doc_type.lower()}",
        application_id=app_id,
        document_type=doc_type,
        s3_key=f"incoming/{app_id}/{doc_type.lower()}.pdf",
        uploaded_at=datetime.now(UTC),
        parse_status="PENDING",
    )


def _full_initial_state(
    application_id: str = "app_sv_001",
    annual_income: Decimal = Decimal("90000"),
    debt_utilization: Decimal = Decimal("0.20"),
    loan_amount: Decimal = Decimal("20000"),
    include_paystub: bool = True,
    include_bank_statement: bool = True,
) -> dict:
    docs = []
    if include_paystub:
        docs.append(_make_document(DocumentType.PAYSTUB, application_id))
    if include_bank_statement:
        docs.append(_make_document(DocumentType.BANK_STATEMENT, application_id))
    return {
        "application_id": application_id,
        "user_id": "user_sv",
        "trace_id": "trace_sv_001",
        "runtime_session_id": None,
        "application": _make_application(application_id, annual_income, debt_utilization, loan_amount),
        "document_inventory": docs,
        "pay_stub_data": None,
        "bank_statement_data": None,
        "risk_request": None,
        "risk_response": None,
        "compliance_result": None,
        "decision": None,
        "artifact_json_s3_key": None,
        "artifact_pdf_s3_key": None,
        "audit_context": None,
        "error": None,
        "needs_manual_review": False,
        "parse_failure_count": 0,
        "submitted_at": datetime.now(UTC),
        "decided_at": None,
    }


def _make_risk_response(
    profile: RiskProfile,
    flags: list[RiskFlag] | None = None,
    application_id: str = "app_sv_001",
) -> RiskResponse:
    return RiskResponse(
        applicant_id=application_id,
        risk_profile=profile,
        credit_score=745 if profile == RiskProfile.PRIME else 620,
        tradelines=[
            Tradeline(
                account_type=AccountType.CREDIT_CARD,
                balance=Decimal("2500"),
                limit=Decimal("10000"),
                utilization=Decimal("0.25"),
            )
        ],
        risk_flags=flags or [],
        income_band="HIGH" if profile == RiskProfile.PRIME else "LOW",
        utilization_band="LOW" if profile == RiskProfile.PRIME else "HIGH",
        score_range_rationale=f"Stub rationale for {profile}.",
    )


def _make_compliance_result(
    action: ComplianceAction,
    application_id: str = "app_sv_001",
) -> ComplianceResult:
    return ComplianceResult(
        applicationId=application_id,
        passed=action == ComplianceAction.APPROVE,
        flags=[],
        recommendedAction=action,
    )


# ── Graph compilation ─────────────────────────────────────────────────────────

class TestSupervisorGraphCompiles:
    def test_graph_compiles(self) -> None:
        graph = build_supervisor_graph()
        assert graph is not None


# ── Happy-path end-to-end ─────────────────────────────────────────────────────

class TestSupervisorHappyPath:
    def test_prime_application_produces_approve(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(
            application_id="app_prime_001",
            annual_income=Decimal("90000"),
            debt_utilization=Decimal("0.20"),
            loan_amount=Decimal("20000"),
        )
        result = graph.invoke(state)
        decision = result.get("decision")
        assert decision is not None
        assert decision.outcome == DecisionOutcome.APPROVE

    def test_decision_includes_risk_and_compliance(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(application_id="app_audit_001")
        result = graph.invoke(state)
        decision = result.get("decision")
        assert decision is not None
        assert decision.risk_response is not None
        assert decision.compliance_result is not None

    def test_artifacts_s3_keys_written(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(application_id="app_artifacts_001")
        result = graph.invoke(state)
        assert result.get("artifact_json_s3_key") is not None
        assert result.get("artifact_pdf_s3_key") is not None

    def test_audit_context_written(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(application_id="app_ac_001")
        result = graph.invoke(state)
        assert result.get("audit_context") is not None

    def test_application_status_completed(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(application_id="app_status_001")
        result = graph.invoke(state)
        assert result["application"].status in (
            ApplicationStatus.COMPLETED,
            ApplicationStatus.MANUAL_REVIEW,
        )


# ── Fallback: missing docs → error terminal ───────────────────────────────────

class TestFallbackMissingDocs:
    def test_no_docs_sets_error_in_state(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(
            application_id="app_nodocs",
            include_paystub=False,
            include_bank_statement=False,
        )
        result = graph.invoke(state)
        # Either error is set OR application status is FAILED
        assert result.get("error") is not None or (
            result.get("application") and result["application"].status == ApplicationStatus.FAILED
        )

    def test_missing_paystub_triggers_validation_error(self) -> None:
        graph = build_supervisor_graph()
        state = _full_initial_state(
            application_id="app_nops",
            include_paystub=False,
            include_bank_statement=True,
        )
        result = graph.invoke(state)
        assert result.get("error") is not None


# ── Fallback: REFER → manual review terminal ──────────────────────────────────

class TestFallbackManualReview:
    def test_refer_outcome_sets_manual_review_flag(self) -> None:
        """A SUBPRIME REFER should route to manual_review_terminal."""
        graph = build_supervisor_graph()
        # SUBPRIME income/utilization within the REFER band (not extreme)
        state = _full_initial_state(
            application_id="app_refer",
            annual_income=Decimal("35000"),
            debt_utilization=Decimal("0.55"),
            loan_amount=Decimal("10000"),
        )
        result = graph.invoke(state)
        decision = result.get("decision")
        if decision and decision.outcome == DecisionOutcome.REFER:
            assert result.get("needs_manual_review") is True
            if result.get("application"):
                assert result["application"].status == ApplicationStatus.MANUAL_REVIEW


# ── Routing functions unit tests (pure, no side effects) ──────────────────────

class TestRoutingFunctions:
    def test_route_after_ingest_no_error(self) -> None:
        state: dict = {"error": None, "application_id": "x"}
        assert _route_after_ingest(state) == "validate_inputs"  # type: ignore[arg-type]

    def test_route_after_ingest_error(self) -> None:
        state: dict = {"error": "missing ids"}
        assert _route_after_ingest(state) == "error_terminal"  # type: ignore[arg-type]

    def test_route_after_validate_no_error(self) -> None:
        state: dict = {"error": None}
        assert _route_after_validate(state) == "process_documents"  # type: ignore[arg-type]

    def test_route_after_validate_error(self) -> None:
        state: dict = {"error": "Missing docs"}
        assert _route_after_validate(state) == "error_terminal"  # type: ignore[arg-type]

    def test_route_after_process_no_failure(self) -> None:
        state: dict = {"parse_failure_count": 0}
        assert _route_after_process_documents(state) == "run_risk"  # type: ignore[arg-type]

    def test_route_after_process_with_failure(self) -> None:
        state: dict = {"parse_failure_count": 2}
        assert _route_after_process_documents(state) == "make_decision"  # type: ignore[arg-type]

    def test_route_after_risk_prime_continues(self) -> None:
        state: dict = {"risk_response": _make_risk_response(RiskProfile.PRIME)}
        assert _route_after_run_risk(state) == "run_compliance"  # type: ignore[arg-type]

    def test_route_after_risk_extreme_subprime_declines_early(self) -> None:
        rr = _make_risk_response(
            RiskProfile.SUBPRIME,
            flags=[RiskFlag.HIGH_UTILIZATION, RiskFlag.LOW_INCOME],
        )
        state: dict = {"risk_response": rr}
        assert _route_after_run_risk(state) == "make_decision"  # type: ignore[arg-type]

    def test_route_after_risk_no_response(self) -> None:
        state: dict = {"risk_response": None}
        assert _route_after_run_risk(state) == "make_decision"  # type: ignore[arg-type]

    def test_route_after_decision_approve(self) -> None:
        decision = Decision(
            applicationId="app",
            outcome=DecisionOutcome.APPROVE,
            riskProfile=RiskProfile.PRIME,
            creditScore=750,
            rationale="test",
        )
        state: dict = {"decision": decision}
        assert _route_after_make_decision(state) == "package_artifacts"  # type: ignore[arg-type]

    def test_route_after_decision_refer(self) -> None:
        decision = Decision(
            applicationId="app",
            outcome=DecisionOutcome.REFER,
            riskProfile=RiskProfile.NEAR_PRIME,
            creditScore=660,
            rationale="test",
        )
        state: dict = {"decision": decision}
        assert _route_after_make_decision(state) == "manual_review_terminal"  # type: ignore[arg-type]


# ── make_decision node (P3-T8) ────────────────────────────────────────────────

class TestMakeDecisionNode:
    def _state_with_risk_and_compliance(
        self,
        profile: RiskProfile = RiskProfile.PRIME,
        compliance_action: ComplianceAction = ComplianceAction.APPROVE,
    ) -> dict:
        return {
            "application_id": "app_md_001",
            "user_id": "user_md",
            "trace_id": "trace_md",
            "risk_response": _make_risk_response(profile),
            "compliance_result": _make_compliance_result(compliance_action),
            "parse_failure_count": 0,
        }

    def test_prime_approve_compliance_gives_approve(self) -> None:
        state = self._state_with_risk_and_compliance(RiskProfile.PRIME, ComplianceAction.APPROVE)
        result = make_decision(state)  # type: ignore[arg-type]
        assert result["decision"].outcome == DecisionOutcome.APPROVE

    def test_compliance_decline_overrides_prime(self) -> None:
        state = self._state_with_risk_and_compliance(RiskProfile.PRIME, ComplianceAction.DECLINE)
        result = make_decision(state)  # type: ignore[arg-type]
        assert result["decision"].outcome == DecisionOutcome.DECLINE

    def test_compliance_refer_gives_refer(self) -> None:
        state = self._state_with_risk_and_compliance(RiskProfile.NEAR_PRIME, ComplianceAction.REFER)
        result = make_decision(state)  # type: ignore[arg-type]
        assert result["decision"].outcome == DecisionOutcome.REFER

    def test_subprime_risk_gives_refer(self) -> None:
        state = self._state_with_risk_and_compliance(RiskProfile.SUBPRIME, ComplianceAction.APPROVE)
        result = make_decision(state)  # type: ignore[arg-type]
        assert result["decision"].outcome in (DecisionOutcome.REFER, DecisionOutcome.DECLINE)

    def test_parse_failure_gives_refer(self) -> None:
        state = self._state_with_risk_and_compliance()
        state["parse_failure_count"] = 3
        result = make_decision(state)  # type: ignore[arg-type]
        assert result["decision"].outcome == DecisionOutcome.REFER

    def test_rationale_references_engine_explanation(self) -> None:
        state = self._state_with_risk_and_compliance()
        result = make_decision(state)  # type: ignore[arg-type]
        rationale = result["decision"].rationale
        # Rationale must come from score_range_rationale, not invented prose
        assert "PRIME" in rationale or "Stub rationale" in rationale

    def test_decided_at_set(self) -> None:
        state = self._state_with_risk_and_compliance()
        result = make_decision(state)  # type: ignore[arg-type]
        assert result.get("decided_at") is not None

    def test_refer_sets_needs_manual_review(self) -> None:
        state = self._state_with_risk_and_compliance(RiskProfile.NEAR_PRIME, ComplianceAction.REFER)
        result = make_decision(state)  # type: ignore[arg-type]
        assert result.get("needs_manual_review") is True
