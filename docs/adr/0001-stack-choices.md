# ADR 0001 – Core Stack & Technology Choices

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-22 |
| Author | Solo builder |
| Deciders | Solo builder |

---

## Context

We are building a production-quality side project that demonstrates an enterprise-style, agentic consumer loan origination system. The goal is to validate cloud-native AI orchestration patterns without requiring real-world credit bureau integrations or production-scale data. Key constraints:

1. **Solo builder** — implementation complexity must be manageable for one developer.
2. **Enterprise-upgradable** — every mocked service (risk engine, doc parser) sits behind a stable interface contract so it can be replaced with a real provider by swapping only the implementation.
3. **AWS-native** — the system must be demonstrably deployable on AWS using managed services.
4. **Deterministic** — all non-LLM outputs must be deterministic and replay-testable.
5. **Production discipline** — security, observability, and IaC patterns should mirror what a real team would build.

---

## Decisions

### D1 — LangGraph for agent orchestration (over custom state-machine code or plain LangChain)

**Decision:** Use LangGraph with a Supervisor graph + specialist subgraphs.

**Rationale:**
- LangGraph provides first-class typed-state management, conditional edges, and subgraph composition — the primitives needed for multi-step underwriting workflows.
- The Supervisor + Specialist pattern (document, risk, compliance, packaging subgraphs) maps directly onto the loan origination workflow phases and keeps each subgraph independently testable.
- LangGraph nodes accept and emit typed state, which prevents the "unconstrained LLM prose" anti-pattern that requirements §5.1 prohibits for business-critical decisions.

**Alternatives considered:**
- _Raw LangChain LCEL chains_ — insufficient state management and no first-class graph/branching support.
- _Custom Python state machine_ — re-invents LangGraph without the tooling ecosystem.

---

### D2 — Amazon Bedrock AgentCore Runtime & Gateway for agent hosting and tool routing

**Decision:** Use AgentCore Runtime to host the LangGraph application and AgentCore Gateway to expose tool contracts.

**Rationale:**
- AgentCore Runtime provides a managed hosting surface for LangGraph-based agents on AWS without needing a custom container orchestration setup.
- AgentCore Gateway standardizes tool invocation behind a stable interface (IAM-backed, upgradeable to JWT/OIDC), keeping the tool boundary production-like while using only IAM credentials during the side-project phase.
- The Gateway boundary means swapping a mock tool (`risk_engine.evaluate`) for a real bureau integration requires only a new Gateway target registration, not an orchestration change.

**Trade-off:** Terraform coverage of AgentCore is incomplete at the time of writing. A boto3/CLI wrapper (`infra/modules/agentcore/`) provides an idempotent automation path. This is tracked as the highest-risk item in the Phase 1 plan.

---

### D3 — Terraform for all infrastructure (over CDK, SAM, or ClickOps)

**Decision:** Terraform with modular layout (`infra/modules/`, `infra/envs/`).

**Rationale:**
- Terraform's provider ecosystem is the most mature for AWS; HCL modules map cleanly to the network / IAM / storage / auth / observability decomposition in design §11.
- A modular structure enables composable env promotions in the future (dev → stage → prod) without rewriting.
- Terraform state (S3 + DynamoDB lock) provides reproducibility and collaborative safety even for a solo project.

**Alternatives considered:**
- _AWS CDK_ — viable but couples infra to Node/Python SDK versions; HCL is more auditable by security reviewers who are unfamiliar with CDK constructs.
- _SAM_ — too serverless-centric; the ALB + private-subnet topology is a poor fit.

---

### D4 — LlamaParse (Llama Cloud) for document parsing (over Textract or custom PDF extraction)

**Decision:** Use LlamaParse for pay stub and bank statement extraction.

**Rationale:**
- LlamaParse supports guided extraction with parse instructions tailored for financial documents; it can reliably extract structured fields (gross pay, transactions, balances) from varied PDF layouts.
- The upload → parse job → poll pattern is async and maps cleanly onto an AgentCore Gateway tool wrapper.
- It avoids building and maintaining a custom extraction pipeline for the side-project scope.

**Trade-off:** Extraction quality varies across PDF templates. Mitigated by: (a) per-document-type parse profiles, (b) a tolerant normalization layer with explicit `confidence_notes` surfacing, and (c) pinned fixture PDFs for unit/integration tests.

---

### D5 — Deterministic mock risk engine (over real bureau integration or a probabilistic ML model)

**Decision:** Implement a pure-function mock engine with explicit scoring rules in `config/risk_policy.yaml`.

**Rationale:**
- Requirements §5.3 explicitly prohibit real bureau integrations; a mock engine preserves the same architectural boundary.
- Determinism (same input → same output) is essential for replay tests, golden-case evaluation, and drift detection.
- Transparent rules (PRIME/NEAR_PRIME/SUBPRIME thresholds) make the system explainable and independently auditable.
- The mock sits behind the identical `risk_engine.evaluate` Gateway contract, so swapping it for a real provider is a single implementation change.

---

### D6 — FastAPI + Pydantic v2 for the backend API

**Decision:** FastAPI with Pydantic v2 models, async I/O throughout, and DI via `Depends`.

**Rationale:**
- FastAPI's native async support is essential for non-blocking S3 uploads, AgentCore Runtime session starts, and JWT validation.
- Pydantic v2 strict validation with camelCase aliases satisfies the "stable external contract" requirement.
- `Depends`-based DI makes auth, settings, and repositories testable via dependency override without test-specific branches in production code.

---

### D7 — Amazon Cognito for user authentication (over Auth0, Okta, or custom)

**Decision:** Cognito User Pools with PKCE-based OIDC flow for the React SPA.

**Rationale:**
- Cognito issues standard JWTs, integrates with IAM via identity pools if needed, and supports group-based role claims (`cognito:groups`).
- OIDC compatibility means the backend JWT validator is identity-provider-agnostic — switching to Auth0 or an enterprise IdP later requires only a JWKS URI and claim-mapping change.
- Two Cognito groups (`LoanOfficer`, `Operator`) implement the role separation required by design §4.3 with zero custom code.

---

### D8 — UV for all Python dependency management

**Decision:** UV exclusively. No pip, poetry, or conda.

**Rationale:**
- UV provides a unified workspace model that manages cross-package editable installs, lockfile generation, and virtualenv creation in a single tool.
- Speed: UV resolves and installs significantly faster than pip/poetry, which matters in CI.
- Lockfile (`uv.lock`) ensures bit-for-bit reproducibility across developer and CI environments.
- The `[tool.uv.sources]` workspace source mechanism replaces local path dependencies with a cleaner, version-aware interface.

---

### D9 — React 19 + Vite + TypeScript (strict) for the frontend

**Decision:** Vite with `@vitejs/plugin-react`, React 19, TypeScript strict mode, ESLint 9 flat config, Prettier.

**Rationale:**
- Vite's HMR and fast cold-start support productive local development.
- TypeScript strict mode + ESLint enforces the API hook / error-boundary patterns required by the tech rules.
- React Router v7 provides nested layouts and loader-based data patterns for the multi-view (intake → status → decision) flow.

---

## Consequences

- All tool interfaces must be versioned in `shared/schemas/` before implementation in later phases.
- Any change to a tool's JSON contract must be treated as a breaking change and tracked in the OpenAPI snapshot.
- The `RUNTIME_MODE=local` backend/agent environment variable must be honored at every phase so the system remains runnable locally without cloud infrastructure.
- The secrets convention (`.env` files, never committed) must be enforced by pre-commit hooks and CI from Phase 0 onward.
- The deterministic mock risk engine's scoring rules are the ground truth for the evaluation harness. Any change to `config/risk_policy.yaml` requires re-baselining all golden cases.
