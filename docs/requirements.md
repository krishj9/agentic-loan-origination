# Requirements Document – Agentic Loan Origination Side Project (LangGraph + AgentCore + Terraform)

## 1. Purpose and scope

- Build a production-quality side project that demonstrates an enterprise-style, agentic loan origination workflow on AWS using Amazon Bedrock AgentCore Runtime and Gateway, LangGraph for orchestration, and Terraform for infrastructure.[web:195][web:81]
- The system must avoid real credit bureau integrations and instead use a deterministic mock risk engine that preserves the same architectural patterns as a production implementation.[web:81]
- Document processing must use LlamaParse via Llama Cloud to extract structured data from uploaded financial PDFs such as pay stubs and bank statements.[web:103][web:203]

## 2. Stakeholders and usage model

- The primary builder/operator is a single developer running a side project with production-style operational discipline.
- Demo users include loan officers or reviewers who submit synthetic applications, upload synthetic supporting documents, and review decisions and explanations.
- The architecture should remain enterprise-upgradable so that mocked services can later be replaced with real providers without changing the orchestration pattern.

## 3. Core capabilities

The system must support:

1. Loan application intake through a UI and API.
2. Secure upload of synthetic PDFs into S3.
3. Document parsing and normalization using LlamaParse.[web:103][web:203]
4. Mock credit risk evaluation through an AgentCore Gateway tool with deterministic outputs.[web:81][web:195]
5. Mock compliance evaluation through rule-based checks.
6. Decisioning, explanation generation, and archival of JSON/PDF outputs.
7. Observability, evaluation harnesses, and guardrails for safe iteration.[web:195][web:196]

## 4. Platform and infrastructure requirements

### 4.1 Cloud platform

- The system must run on AWS, using Amazon Bedrock AgentCore Runtime and Gateway for agent hosting and tool access.[web:195][web:196]
- Amazon S3 must be used for raw uploads, extracted artifacts, and archived decision packages.
- Amazon CloudWatch must be used for logs, metrics, and operational visibility.
- Amazon Cognito should be used for user authentication for UI and API access, because Cognito user pools issue JWTs for applications and OIDC-compatible flows.[web:82][web:197][web:199]

### 4.2 VPC, networking, and security

- The deployment must use a dedicated VPC with at least two Availability Zones, public subnets for ingress, and private subnets for internal application workloads.
- Terraform must define VPCs, subnets, route tables, internet gateways, NAT gateways, security groups, and load balancers as part of the baseline environment.
- TLS termination must occur at an Application Load Balancer or API Gateway, and HTTPS must be enforced end to end.
- Security groups must restrict traffic so that only the load balancer can reach internal app services, and only approved services can reach mock tool backends.

### 4.3 AgentCore and Gateway

- AgentCore Runtime must host the LangGraph-based supervisor and specialist agents.[web:196]
- AgentCore Gateway must expose internal tools for document parsing, mock risk evaluation, compliance checks, and packaging via a stable tool interface.[web:195][web:201]

#### Security and authentication

- Default side-project mode may use API key or IAM-based authentication for Gateway tool access, while remaining upgradeable to JWT/OIDC-based inbound authorization for broader access patterns.[web:81][web:195][web:196]
- The system should include Amazon Cognito for user authentication for the UI and API, and the design should remain compatible with future OAuth2/OIDC enterprise integration because Cognito user pools issue JWTs and support OIDC-based flows.[web:82][web:197][web:199]
- Access control must separate at least two role classes:
  - Loan officers/reviewers: submit applications and review decisions.
  - System operators/admins: configure rules, inspect logs, and manage infrastructure.
- Gateway tools must be restricted by IAM policies and least-privilege execution roles.

#### Transport security and auditability

- TLS must be enforced for all UI, API, and tool traffic.
- The system must log authentication attempts, especially failed access attempts, for audit and operational visibility.
- Decision artifacts stored in S3 must include metadata such as `user_id`, `application_id`, and decision timestamp for auditability.

## 5. Application-level requirements

### 5.1 Agents and orchestration

- LangGraph must be used to implement the supervisor workflow and specialist subgraphs for document processing, credit risk, compliance, and packaging.
- Agent outputs must be structured JSON objects, and business-critical decisions must not depend solely on unconstrained LLM prose.

### 5.2 LlamaParse-based form processing

- LlamaParse via Llama Cloud must be the default document parsing mechanism for uploaded PDFs.[web:103][web:203]
- Parsing instructions must be tailored for financial documents so the parser extracts fields such as employer, pay period, gross pay, net pay, account balances, transactions, and other underwriting-relevant values.[web:103]
- Parsed output must be normalized into a canonical application schema stored in S3.

### 5.3 Mock credit bureau / risk engine

#### Requirements

The system must implement a mock risk engine with:

- Configurable scoring curves.
- Synthetic tradelines and utilization.
- Deterministic output for a given input for repeatability.
- Exposure as a Gateway tool named `risk_engine.evaluate` with a stable JSON schema.
- Support for multiple risk buckets: `PRIME`, `NEAR_PRIME`, and `SUBPRIME`.
- Bucket selection driven by either:
  - Synthetic financial attributes such as `annual_income` and `debt_utilization`, or
  - An explicit `risk_profile` override field for testing.
- Fully documented rules so outputs are explainable and testable.

#### Example rules

- Prime: `annual_income > 80,000` and `debt_utilization < 30%` leading to a score range of 720–800.
- Near-prime: `annual_income` between 40,000–80,000 or `debt_utilization` between 30–60% leading to a score range of 620–700.
- Subprime: `annual_income < 40,000` or `debt_utilization > 60%` leading to a score range of 500–600.

These ranges are product requirements for the side project rather than external credit-bureau standards, and they must remain deterministic once encoded in the mock engine.

#### Example JSON schema

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

#### Mocking behavior requirements

- The mock engine must accept canonical application inputs and produce the same output for the same input values.
- Synthetic tradelines should be derived from deterministic seed logic or deterministic formulas rather than uncontrolled randomness.
- Risk flags such as `HIGH_UTILIZATION` and `LOW_INCOME` must be derived from transparent rules and included in the response for explainability.
- The supervisor and credit risk agent must treat the mock response as if it came from an external provider, so the architectural contract remains production-like.

### 5.4 Compliance layer

- Compliance checks should be deterministic and rule based.
- Rules must be externalized into configuration files where feasible.
- The compliance layer must produce structured pass/fail outputs, issue flags, and a recommended action such as `APPROVE`, `REFER`, or `DECLINE`.

## 6. Sample PDFs and test data requirements

- The system must use only synthetic or template-based data, never real customer documents.
- The project documentation should instruct users to obtain sample pay stub templates and bank statement templates from public template providers and then populate them with synthetic values before exporting to PDF.
- Sample bank statement templates or example statements must likewise be synthetic or template-based before use in the system.

### 6.1 Sample PDF preparation and upload procedure

The project documentation must include an explicit operating procedure for obtaining, preparing, and uploading synthetic PDF documents for loan processing.

#### Approved document types for the first implementation

The initial scope should support only these document types:

- Pay stubs
- Bank statements

This limited set is sufficient to demonstrate upload, parsing, normalization, underwriting inputs, and end-to-end decisioning without adding unnecessary document complexity.

#### Approved sources for sample documents

Sample pay stubs may be created from public templates such as:

- Smartsheet pay stub templates.
- Template.net pay stub PDF templates.
- Jotform pay stub PDF templates.

Sample bank statements may be created from public templates such as:

- Template.net bank statement templates.
- Jotform bank statement PDF templates.
- Other editable statement-template providers when the content is converted to fully synthetic data before use.

#### Rules for synthetic content

- No real personal, employment, or banking data may be used.
- All names, addresses, account numbers, employers, dates, and balances must be synthetic.
- Account numbers should be masked or synthetic, for example using only a fake last four digits.
- Documents should be internally consistent across the application package, for example matching applicant name and income values between the application form, pay stub, and bank statement.

#### Minimum required fields in pay stub PDFs

Each uploaded pay stub should contain at least:

- Employee full name
- Employer name
- Pay period start date and end date
- Pay date
- Gross pay
- Deductions/taxes
- Net pay
- Optional but recommended YTD values

#### Minimum required fields in bank statement PDFs

Each uploaded bank statement should contain at least:

- Account holder name
- Statement date range
- Account number or masked last four digits
- Opening balance
- Transaction rows including date, description, and amount
- Closing balance

#### File-preparation procedure

1. Download a public template in PDF or editable format.
2. Populate it with synthetic applicant and financial data.
3. Export the completed document to PDF if it is not already in PDF format.
4. Verify the PDF is readable, not password-protected, and not a blurred image scan.
5. Use a consistent naming convention such as:
   - `paystub_<applicant>_<month>_<year>.pdf`
   - `bank_statement_<applicant>_<month>_<year>.pdf`

#### Recommended upload package per demo application

Each demo application should initially upload:

- One pay stub PDF
- One bank statement PDF

This is the minimum document set recommended for the first end-to-end workflow using LlamaParse.[web:103]

#### Recommended test scenarios

The project should maintain at least three synthetic document packs:

- PRIME applicant pack
- NEAR_PRIME applicant pack
- SUBPRIME applicant pack

Each pack should contain internally consistent PDFs aligned with the mock risk-engine rules and expected decision labels.

## 7. Observability, evaluation, and guardrails

### 7.1 Observability

- Runtime, API, and tool invocation traces must be logged to CloudWatch and correlated using application IDs and session IDs.
- Authentication attempts and authorization failures must be logged for operational and audit visibility.

### 7.2 Evaluation harness

- Maintain a set of synthetic golden applications with expected decisions.
- Each golden case must include:
  - Applicant metadata.
  - Uploaded synthetic documents.
  - Expected risk profile.
  - Expected decision outcome.
- The harness must run replay tests by:
  - Submitting golden applications through the API.
  - Comparing returned decision JSON against expected labels.
  - Logging mismatches to CloudWatch.

### 7.3 Evaluation metrics

The system must calculate or report at least these evaluation metrics:

- Accuracy as percentage of matched decisions.
- False-positive and false-negative counts for decision mismatches.
- Drift detection when observed scoring deviates from deterministic mock-engine rules.

### 7.4 Guardrails

- Amazon Bedrock Guardrails should be used for prompt/response safety where LLM interactions are involved.[web:196]
- Guardrails should be applied to agent interactions where free-form model input/output exists, but structured tool outputs must still be validated by application logic.[web:196]
- Sensitive-information controls should be treated as supportive safeguards rather than the only control for structured redaction.
