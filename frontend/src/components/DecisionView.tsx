/**
 * Decision review view with structured decision details and artifact downloads.
 */

import { useParams } from 'react-router-dom';
import { useDecision } from '../hooks/useApi';
import { Button, Card, LoadingSpinner, ErrorMessage } from './ui';
import { DecisionOutcome, RiskProfile } from '../types';
import { getApiConfig } from '../config/api';

export function DecisionView() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const { data: decision, isLoading, error } = useDecision(applicationId!);

  const handleDownload = (s3Key: string) => {
    // In production, this would generate a presigned download URL from backend
    // For now, construct direct URL (requires proper CORS and bucket policy)
    const apiConfig = getApiConfig();
    const downloadUrl = `${apiConfig.baseUrl}/download?key=${encodeURIComponent(s3Key)}`;
    
    // Open in new tab
    window.open(downloadUrl, '_blank');
  };

  if (isLoading) {
    return (
      <Card title="Application Decision">
        <LoadingSpinner size="lg" label="Loading decision..." />
      </Card>
    );
  }

  if (error) {
    return (
      <Card title="Application Decision">
        <ErrorMessage error={error} title="Failed to load decision" />
        <p className="decision-view__hint">
          The decision may not be available yet. Please check the application status.
        </p>
      </Card>
    );
  }

  if (!decision) {
    return (
      <Card title="Application Decision">
        <p>No decision available for this application.</p>
      </Card>
    );
  }

  return (
    <Card title="Application Decision">
      <div className="decision-view">
        {/* Outcome banner */}
        <div className={`decision-view__outcome decision-view__outcome--${decision.outcome.toLowerCase()}`}>
          <OutcomeBadge outcome={decision.outcome} />
          <h2 className="decision-view__outcome-title">
            {getOutcomeTitle(decision.outcome)}
          </h2>
        </div>

        {/* Risk profile and score */}
        <div className="decision-view__risk">
          <div className="decision-view__risk-item">
            <span className="decision-view__label">Risk Profile:</span>
            <RiskProfileBadge profile={decision.riskProfile} />
          </div>
          <div className="decision-view__risk-item">
            <span className="decision-view__label">Credit Score:</span>
            <span className="decision-view__value">{decision.creditScore}</span>
          </div>
        </div>

        {/* Rationale */}
        <div className="decision-view__rationale">
          <h3>Decision Rationale</h3>
          <p>{decision.rationale}</p>
        </div>

        {/* Risk details */}
        {decision.riskResponse && (
          <div className="decision-view__section">
            <h3>Risk Assessment</h3>
            <div className="decision-view__details">
              <dl>
                <dt>Risk Flags:</dt>
                <dd>
                  {decision.riskResponse.riskFlags.length > 0 ? (
                    <ul className="decision-view__flags">
                      {decision.riskResponse.riskFlags.map((flag, idx) => (
                        <li key={idx} className="decision-view__flag">
                          {flag}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span>None</span>
                  )}
                </dd>
                <dt>Tradelines:</dt>
                <dd>{decision.riskResponse.tradelines.length} accounts</dd>
              </dl>
              {decision.riskResponse.scoreRangeRationale && (
                <p className="decision-view__explanation">
                  {decision.riskResponse.scoreRangeRationale}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Compliance results */}
        {decision.complianceResult && (
          <div className="decision-view__section">
            <h3>Compliance Review</h3>
            <div className="decision-view__details">
              <dl>
                <dt>Recommended Action:</dt>
                <dd>{decision.complianceResult.recommendedAction}</dd>
                <dt>Overall Severity:</dt>
                <dd>{decision.complianceResult.overallSeverity}</dd>
                <dt>Flags:</dt>
                <dd>
                  {decision.complianceResult.flags.length > 0 ? (
                    <ul className="decision-view__compliance-flags">
                      {decision.complianceResult.flags.map((flag) => (
                        <li key={flag.flagId} className={`compliance-flag compliance-flag--${flag.severity.toLowerCase()}`}>
                          <strong>{flag.rule}:</strong> {flag.description}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span>No compliance issues</span>
                  )}
                </dd>
              </dl>
            </div>
          </div>
        )}

        {/* Artifacts */}
        <div className="decision-view__artifacts">
          <h3>Decision Documents</h3>
          <div className="decision-view__artifact-buttons">
            {decision.artifactJsonS3Key && (
              <Button
                variant="secondary"
                onClick={() => handleDownload(decision.artifactJsonS3Key!)}
              >
                Download JSON
              </Button>
            )}
            {decision.artifactPdfS3Key && (
              <Button
                variant="secondary"
                onClick={() => handleDownload(decision.artifactPdfS3Key!)}
              >
                Download PDF Report
              </Button>
            )}
          </div>
        </div>

        {/* Audit context */}
        {decision.auditContext && (
          <details className="decision-view__audit">
            <summary>Audit Information</summary>
            <dl>
              <dt>User ID:</dt>
              <dd>{decision.auditContext.userId}</dd>
              <dt>Submission Time:</dt>
              <dd>{new Date(decision.auditContext.submissionTimestamp).toLocaleString()}</dd>
              {decision.auditContext.decisionTimestamp && (
                <>
                  <dt>Decision Time:</dt>
                  <dd>{new Date(decision.auditContext.decisionTimestamp).toLocaleString()}</dd>
                </>
              )}
              {decision.auditContext.runtimeSessionId && (
                <>
                  <dt>Runtime Session ID:</dt>
                  <dd><code>{decision.auditContext.runtimeSessionId}</code></dd>
                </>
              )}
            </dl>
          </details>
        )}
      </div>
    </Card>
  );
}

function OutcomeBadge({ outcome }: { outcome: DecisionOutcome }) {
  const config = {
    [DecisionOutcome.APPROVE]: { label: 'Approved', icon: '✓' },
    [DecisionOutcome.REFER]: { label: 'Referred', icon: '→' },
    [DecisionOutcome.DECLINE]: { label: 'Declined', icon: '✗' },
  };

  const { label, icon } = config[outcome];

  return (
    <span className={`outcome-badge outcome-badge--${outcome.toLowerCase()}`}>
      <span className="outcome-badge__icon">{icon}</span>
      <span className="outcome-badge__label">{label}</span>
    </span>
  );
}

function RiskProfileBadge({ profile }: { profile: RiskProfile }) {
  return (
    <span className={`risk-profile-badge risk-profile-badge--${profile.toLowerCase()}`}>
      {profile}
    </span>
  );
}

function getOutcomeTitle(outcome: DecisionOutcome): string {
  const titles = {
    [DecisionOutcome.APPROVE]: 'Application Approved',
    [DecisionOutcome.REFER]: 'Manual Review Required',
    [DecisionOutcome.DECLINE]: 'Application Declined',
  };
  return titles[outcome];
}
