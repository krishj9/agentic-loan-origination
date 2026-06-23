/**
 * TypeScript types mirroring shared/schemas canonical Pydantic models.
 * These types ensure frontend-backend contract alignment.
 */

// Enums matching shared/schemas/enums.py
export enum RiskProfile {
  PRIME = 'PRIME',
  NEAR_PRIME = 'NEAR_PRIME',
  SUBPRIME = 'SUBPRIME',
}

export enum DocumentType {
  PAYSTUB = 'PAYSTUB',
  BANK_STATEMENT = 'BANK_STATEMENT',
  ID = 'ID',
  OTHER = 'OTHER',
}

export enum DecisionOutcome {
  APPROVE = 'APPROVE',
  REFER = 'REFER',
  DECLINE = 'DECLINE',
}

export enum ApplicationStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  MANUAL_REVIEW = 'MANUAL_REVIEW',
}

export enum AccountType {
  CREDIT_CARD = 'CREDIT_CARD',
  AUTO_LOAN = 'AUTO_LOAN',
  MORTGAGE = 'MORTGAGE',
}

export enum RiskFlag {
  HIGH_UTILIZATION = 'HIGH_UTILIZATION',
  LOW_INCOME = 'LOW_INCOME',
  NEAR_PRIME_INCOME = 'NEAR_PRIME_INCOME',
  MODERATE_UTILIZATION = 'MODERATE_UTILIZATION',
}

export enum ComplianceSeverity {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

export enum ComplianceAction {
  APPROVE = 'APPROVE',
  REFER = 'REFER',
  DECLINE = 'DECLINE',
}

// Document model matching shared/schemas/application.py
export interface Document {
  documentId: string;
  applicationId: string;
  documentType: DocumentType;
  s3Key: string;
  uploadedAt: string;
  parseStatus: string;
}

// Audit context matching shared/schemas/audit.py
export interface AuditContext {
  userId: string;
  applicationId: string;
  submissionTimestamp: string;
  decisionTimestamp?: string;
  runtimeSessionId?: string;
  traceId?: string;
}

// Transaction for bank statements
export interface Transaction {
  date: string;
  description: string;
  amount: string;
}

// Pay stub fields matching shared/schemas/documents.py
export interface PayStubFields {
  employeeName?: string;
  employerName?: string;
  payPeriodStart?: string;
  payPeriodEnd?: string;
  payDate?: string;
  grossPay?: string;
  netPay?: string;
  deductions?: string;
  ytdGrossPay?: string;
  ytdNetPay?: string;
  confidenceNotes?: string;
}

// Bank statement fields matching shared/schemas/documents.py
export interface BankStatementFields {
  accountHolderName?: string;
  statementPeriodStart?: string;
  statementPeriodEnd?: string;
  maskedAccountNumber?: string;
  openingBalance?: string;
  closingBalance?: string;
  transactions?: Transaction[];
  confidenceNotes?: string;
}

// Canonical application matching shared/schemas/application.py
export interface CanonicalApplication {
  applicationId: string;
  userId: string;
  applicantName: string;
  annualIncome: string;
  requestedLoanAmount: string;
  debtUtilization: string;
  status: ApplicationStatus;
  documentInventory?: Document[];
  payStubData?: PayStubFields;
  bankStatementData?: BankStatementFields;
  auditContext?: AuditContext;
}

// Tradeline matching shared/schemas/risk.py
export interface Tradeline {
  accountType: AccountType;
  balance: string;
  limit: string;
  utilization: string;
}

// Risk request matching shared/schemas/risk.py
export interface RiskRequest {
  applicantId: string;
  annualIncome: string;
  debtUtilization: string;
  riskProfile?: RiskProfile;
}

// Risk response matching shared/schemas/risk.py
export interface RiskResponse {
  applicantId: string;
  riskProfile: RiskProfile;
  creditScore: number;
  tradelines: Tradeline[];
  riskFlags: RiskFlag[];
  scoreRangeRationale?: string;
}

// Compliance flag matching shared/schemas/compliance.py
export interface ComplianceFlag {
  flagId: string;
  severity: ComplianceSeverity;
  rule: string;
  description: string;
}

// Compliance result matching shared/schemas/compliance.py
export interface ComplianceResult {
  applicationId: string;
  flags: ComplianceFlag[];
  recommendedAction: ComplianceAction;
  overallSeverity: ComplianceSeverity;
  evaluationTimestamp: string;
}

// Decision matching shared/schemas/decision.py
export interface Decision {
  applicationId: string;
  outcome: DecisionOutcome;
  riskProfile: RiskProfile;
  creditScore: number;
  rationale: string;
  riskResponse?: RiskResponse;
  complianceResult?: ComplianceResult;
  artifactJsonS3Key?: string;
  artifactPdfS3Key?: string;
  auditContext?: AuditContext;
}

// API Request/Response types
export interface CreateApplicationRequest {
  applicantName: string;
  annualIncome: string;
  requestedLoanAmount: string;
  debtUtilization: string;
}

export interface CreateApplicationResponse {
  applicationId: string;
  status: ApplicationStatus;
}

export interface UploadDocumentRequest {
  documentType: DocumentType;
}

export interface UploadDocumentResponse {
  documentId: string;
  presignedUrl: string;
  s3Key: string;
}

export interface SubmitApplicationResponse {
  applicationId: string;
  status: ApplicationStatus;
  runtimeSessionId?: string;
}

export interface GetApplicationResponse extends CanonicalApplication {
  // Additional runtime metadata if needed
}

export interface GetDecisionResponse extends Decision {
  // Additional metadata if needed
}

// Error response structure
export interface ApiError {
  detail: string;
  status: number;
  timestamp?: string;
}
