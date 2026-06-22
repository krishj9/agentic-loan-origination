# Design Document – Agentic Loan Origination Side Project (LangGraph + AgentCore + Terraform)

## 1. Overview

This document defines the updated design for a side-project loan origination system built on Amazon Bedrock AgentCore, LangGraph, Terraform, and LlamaParse.[web:195][web:103]
The design assumes synthetic data, mocked credit-risk behavior, and production-style security and observability patterns without requiring enterprise-only dependencies such as real credit bureau contracts.[web:81]

## 2. Design goals

- Preserve an enterprise-like architecture while keeping implementation practical for a solo side project.
- Keep all external dependencies replaceable behind stable tool contracts.
- Make the mock risk engine deterministic, testable, and explainable.
- Use LlamaParse as the document-ingestion path for financial PDFs.
- Keep auth, logging, and audit trails strong enough to demonstrate production discipline.

## 3. Architecture

### 3.1 Logical components

The system is composed of five layers:

- **Client layer** – web UI for application submission and review, plus a programmatic API client.
- **Application/API layer** – accepts applications, uploads PDFs to S3, starts Runtime sessions, and returns status/results.
- **Agent layer** – LangGraph supervisor and specialist subgraphs running in AgentCore Runtime.[web:195][web:196]
- **Tool layer** – AgentCore Gateway exposing document parsing, mock risk, compliance, and packaging tools over stable interfaces.[web:195][web:201]
- **Data/observability layer** – S3, CloudWatch, optional DynamoDB/config stores, and guardrail/audit telemetry.[web:196]

### 3.2 Deployment topology

- Public ingress terminates at an Application Load Balancer or API Gateway over HTTPS.
- Application services run in private subnets.
- AgentCore Runtime hosts the LangGraph application.
- AgentCore Gateway fronts internal tools and standardizes tool access for agents.[web:195]
- S3 stores incoming files, extracted artifacts, and archived decision packages.

## 4. Security and authentication design

### 4.1 User authentication

- The preferred side-project user authentication mechanism is Amazon Cognito user pools for the UI and API, because Cognito supports standard authentication flows and issues JWTs compatible with OIDC-based application patterns.[web:82][web:197][web:199]
- UI users authenticate with Cognito and receive tokens that the API validates before accepting application submissions.

### 4.2 Gateway authentication

- AgentCore Gateway supports multiple inbound authorization modes including IAM-based authorization and JWT-based inbound authorization with OAuth 2.0 compatible identity providers.[web:81][web:195][web:196]
- For this side project, the default should be one of:
  - **IAM-based auth** for agent/runtime-to-tool communication where AWS identities are available.[web:81][web:195]
  - **API key-backed target credentials** for specific downstream mock or proxy services attached through Gateway credential providers.[web:195]
- The design must remain upgradeable to JWT/OIDC inbound auth with Cognito or another IdP when broader end-user access is needed.[web:196][web:197]

### 4.3 Role separation

The system should implement at least two role classes:

- **Loan officer / reviewer role** – create applications, upload documents, and review decisions.
- **Operator / admin role** – update configuration, inspect logs, manage evaluation data, and administer infrastructure.

These roles should be enforced in the UI/API tier and reinforced by IAM permissions for infrastructure and Gateway access.[web:197][web:202]

### 4.4 Transport security and audit

- TLS is mandatory for UI, API, and internal tool ingress.
- Authentication attempts and access failures should be emitted as structured logs into CloudWatch so that operational review and auditability are possible.
- Decision outputs stored in S3 should include metadata such as `application_id`, `user_id`, `submission_timestamp`, `decision_timestamp`, and `runtime_session_id`.

## 5. LangGraph orchestration design

### 5.1 Supervisor graph

The supervisor is the top-level LangGraph workflow and owns end-to-end orchestration.
Recommended node sequence:

1. `ingest_application`
2. `validate_inputs`
3. `process_documents`
4. `run_risk`
5. `run_compliance`
6. `make_decision`
7. `package_artifacts`
8. `persist_and_publish`

Conditional branches should support:

- Missing or invalid documents.
- Document parsing failures.
- Manual-review or refer decisions.
- Early declines for extreme mock risk outcomes.

### 5.2 Shared graph state

The LangGraph state object should include:

- Applicant metadata.
- Document inventory and S3 keys.
- Parsed/normalized financial data.
- Risk-engine request and response objects.
- Compliance findings.
- Final decision, rationale, and generated artifact locations.
- Audit context such as `user_id`, `application_id`, timestamps, and trace/session identifiers.

### 5.3 Specialist subgraphs

Recommended specialist subgraphs:

- **Document/Extraction subgraph** – invokes LlamaParse-backed tools and normalizes output.
- **Risk subgraph** – prepares canonical risk input and calls `risk_engine.evaluate`.
- **Compliance subgraph** – executes deterministic side-project rules.
- **Packaging subgraph** – produces JSON summaries and PDF outputs.

## 6. LlamaParse document-processing design

### 6.1 Parsing model

LlamaParse must be the primary path for pay stub and bank statement ingestion.[web:103][web:203]
The system should use parsing instructions optimized for financial documents because LlamaParse supports guided extraction of structured financial fields and cross-document workflows in underwriting-style pipelines.[web:103][web:203]
Recent LlamaParse guidance for financial-document pipelines also describes a pattern of file upload, parse job creation, and polling for results, which is a good fit for an async tool wrapper.[web:103]

### 6.2 Tool contract

The document parser should be exposed through Gateway as a tool such as `llamaparse.parse_financial_pdf`.
Suggested contract:

- **Input**:
  - `application_id`
  - `document_id`
  - `document_type` (`PAYSTUB`, `BANK_STATEMENT`, `ID`, `OTHER`)
  - `s3_key`
  - `parse_profile`
- **Output**:
  - `raw_markdown`
  - `structured_fields`
  - `table_rows`
  - `confidence_notes`
  - `document_metadata`

### 6.3 Normalization stage

A normalization step should map parser outputs to the system’s canonical schema, including fields such as:

- Employer name.
- Pay period start/end.
- Gross pay and net pay.
- Account holder and statement period.
- Transaction rows and ending balance.

This normalization layer isolates the rest of the system from any parser-specific output differences.

## 7. Mock credit bureau / risk engine design

### 7.1 Design intent

The mock risk engine replaces real bureau integrations while preserving the same architectural boundary: the credit risk agent calls a Gateway-exposed tool that behaves like an external risk provider.[web:195]
This keeps the system realistic while avoiding regulatory and contracting complexity.

### 7.2 Tool contract

The mock risk engine must be exposed as `risk_engine.evaluate`.
The tool should return a stable JSON response that includes at least:

```json
{
  "applicant_id": "string",
  "risk_profile": "PRIME | NEAR_PRIME | SUBPRIME",
  "credit_score": "integer",
  "tradelines": [
    {
      "account_type": "CREDIT_CARD | AUTO_LOAN | MORTGAGE",
      "balance": "number",
      "limit": "number",
      "utilization": "number"
    }
  ],
  "risk_flags": ["HIGH_UTILIZATION", "LOW_INCOME"]
}
```

### 7.3 Deterministic scoring behavior

The engine must produce deterministic outputs for a given input so replay tests remain stable.
Determinism can be implemented through:

- Pure rules using input attributes.
- Seeded synthetic tradeline generation derived from `applicant_id` or `application_id`.
- Stable scoring curves selected from configuration.

### 7.4 Risk profiles and rule mapping

The engine must support three primary buckets:

- **PRIME** – example rule: `annual_income > 80,000` and `debt_utilization < 30%`, target score band 720–800.
- **NEAR_PRIME** – example rule: `annual_income` between 40,000–80,000 or `debt_utilization` between 30–60%, target score band 620–700.
- **SUBPRIME** – example rule: `annual_income < 40,000` or `debt_utilization > 60%`, target score band 500–600.

These are side-project policy bands rather than external credit standards, and they should be maintained in configuration so the evaluation harness can verify them directly.

### 7.5 Override support

The risk input should support an optional `risk_profile` override for testing.
This allows deterministic golden-case creation and explicit regression coverage for PRIME, NEAR_PRIME, and SUBPRIME outcomes.

### 7.6 Tradeline synthesis

Tradelines should be generated in a way that looks realistic but remains deterministic.
A recommended approach is:

- Derive a seed from `applicant_id`.
- Choose 1–5 tradelines from a fixed catalog (`CREDIT_CARD`, `AUTO_LOAN`, `MORTGAGE`).
- Compute balances, limits, and utilization via bounded formulas.
- Emit flags such as `HIGH_UTILIZATION` or `LOW_INCOME` based on rule thresholds.

### 7.7 Explainability

The risk engine should also return or enable derived explanations such as:

- Income band classification.
- Utilization band classification.
- Triggered flags.
- Score-range rationale.

This allows the supervisor to produce human-readable decision justifications without inventing unsupported explanations.

## 8. Compliance design

The compliance subsystem should remain deterministic and lightweight for the side project.
It can run as:

- An internal rules node in the compliance subgraph, or
- A separate Gateway tool if architectural symmetry is preferred.

Recommended checks include:

- Loan amount relative to income.
- Risk-band-specific approval ceilings.
- Required-document completeness.
- Basic synthetic fraud indicators such as duplicate applicant reuse or missing critical fields.

Outputs should include structured flags, severity, and recommended action.

## 9. Packaging and persistence design

### 9.1 Artifact generation

The packaging stage should generate:

- A machine-readable JSON decision summary.
- A human-readable PDF decision package.
- Links or references to source documents and extracted artifacts.

### 9.2 S3 layout

Recommended prefixes:

- `incoming/{application_id}/...`
- `extracted/{application_id}/...`
- `archive/{application_id}/...`

Artifacts in `archive` should include metadata for audit and replay, including user identity and timestamps.

## 10. Observability and evaluation design

### 10.1 Logging and tracing

All major components should emit structured logs with at least:

- `application_id`
- `user_id`
- `runtime_session_id`
- `trace_id`
- `tool_name`
- `decision_outcome`

CloudWatch should be the central sink for application, auth, and replay-harness logs.

### 10.2 Golden-case evaluation harness

The evaluation harness should maintain a catalog of synthetic golden applications.
Each golden case should contain:

- Applicant metadata.
- Uploaded synthetic documents.
- Expected risk profile.
- Expected final decision.

The harness should replay cases through the public or internal API, compare the returned decision JSON against expected labels, and log mismatches to CloudWatch.

### 10.3 Metrics

The harness should report:

- Accuracy as matched-decision percentage.
- False-positive count.
- False-negative count.
- Drift events where actual mock-engine outputs diverge from deterministic configuration.

### 10.4 Guardrails

Amazon Bedrock Guardrails should be associated with agent interactions to reduce unsafe prompt/response behavior and enforce PII-related protections where model-generated content is involved.[web:196]
Because Guardrails sensitive-information filters are probabilistic and context-dependent, structured tool outputs should not rely on Guardrails alone for critical redaction logic.[web:196]

## 11. Terraform infrastructure design

### 11.1 Baseline infrastructure modules

Terraform should define modules for:

- Networking: VPC, subnets, route tables, internet gateway, NAT gateway.
- Security: security groups, IAM roles, policies, KMS keys.
- Edge and ingress: ALB or API Gateway, certificates, DNS if needed.
- Storage: S3 buckets and lifecycle settings.
- Observability: log groups, alarms, dashboards where practical.
- Agent integration hooks: Gateway and Runtime resources where the AWS provider supports them, or wrapper automation if direct resource coverage is incomplete.

### 11.2 Network zoning

Recommended subnet placement:

- Public subnets: ALB, NAT gateways.
- Private app subnets: API/backend services.
- Private data/integration subnets: optional placement for internal mock services if separated.

### 11.3 Firewall model

Security groups should implement these patterns:

- ALB security group: inbound 443 from approved client ranges; outbound to app services.
- App security group: inbound only from ALB security group; outbound only to approved AWS services and mock backends.
- Mock service security group: inbound only from app tier or approved internal caller paths.

### 11.4 Private service access

Where possible, use VPC endpoints for S3 and other AWS services to reduce public egress for internal workloads.

## 12. Sample PDF preparation and upload workflow

### 12.1 Supported initial document set

The first implementation should accept only two document classes:

- Pay stubs
- Bank statements

This keeps the upload and parsing workflow focused while still providing enough financial signal for the mock underwriting flow.

### 12.2 Source and preparation workflow

The operating workflow for sample PDFs should be:

1. Download a public pay stub or bank statement template from an approved source.
2. Populate the template with synthetic applicant data.
3. Export the result as PDF.
4. Upload the PDF through the application UI or API.
5. Store the uploaded file in `incoming/{application_id}/...`.
6. Route the file through the LlamaParse-backed Gateway tool for extraction and normalization.[web:103]

### 12.3 Sample sources

Recommended pay stub sources:

- Smartsheet pay stub templates.
- Template.net pay stub templates.
- Jotform pay stub templates.

Recommended bank statement sources:

- Template.net bank statement templates.
- Jotform bank statement templates.
- Other editable statement-template providers after synthetic replacement of all content.

### 12.4 Content requirements

Each sample PDF should be designed so LlamaParse can extract predictable structured values.
Recommended required fields:

- **Pay stub**: employee name, employer name, pay period, pay date, gross pay, deductions, net pay.
- **Bank statement**: account holder name, statement period, masked account number, opening balance, transactions, closing balance.

### 12.5 Upload quality requirements

Uploaded PDFs should satisfy these rules:

- Digital PDF preferred over photographed image.
- No password protection.
- No multi-document mixing in one file.
- Clear text and tables for parsing.
- Consistent naming conventions for easier traceability.

### 12.6 Demo document packs

The project should maintain reusable synthetic document packs for:

- PRIME
- NEAR_PRIME
- SUBPRIME

Each pack should contain one pay stub and one bank statement whose contents align with the configured mock risk rules and expected golden-case outcomes.

