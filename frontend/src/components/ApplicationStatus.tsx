/**
 * Application submission and status tracking with live polling.
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useSubmitApplication, useApplication, isTerminalStatus } from '../hooks/useApi';
import { Button, Card, LoadingSpinner, ErrorMessage } from './ui';
import { ApplicationStatus as Status } from '../types';

export function ApplicationStatus() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();
  
  const { mutate: submitApplication, isPending: isSubmitting, error: submitError } = useSubmitApplication();
  
  // Poll application status every 3 seconds until terminal
  const {
    data: application,
    isLoading,
    error: fetchError,
    refetch,
  } = useApplication(applicationId!, {
    refetchInterval: 3000,
  });

  // Stop polling when terminal status reached
  useEffect(() => {
    if (application?.status && isTerminalStatus(application.status)) {
      // Polling will naturally stop due to the query being stale
    }
  }, [application?.status]);

  const handleSubmit = () => {
    if (applicationId) {
      submitApplication(applicationId, {
        onSuccess: () => {
          console.log('[ApplicationStatus] Submitted application, polling for status...');
          refetch();
        },
      });
    }
  };

  const handleViewDecision = () => {
    if (applicationId) {
      navigate(`/applications/${applicationId}/decision`);
    }
  };

  const isTerminal = application?.status && isTerminalStatus(application.status);

  // Render loading state
  if (isLoading) {
    return (
      <Card title="Application Status">
        <LoadingSpinner size="lg" label="Loading application..." />
      </Card>
    );
  }

  // Render error state
  if (fetchError) {
    return (
      <Card title="Application Status">
        <ErrorMessage error={fetchError} onRetry={() => refetch()} />
      </Card>
    );
  }

  // Render submit state (before submission)
  if (application?.status === Status.PENDING) {
    return (
      <Card title="Submit Application">
        <div className="application-status">
          <p className="application-status__message">
            Your application is ready to submit. Click below to start processing.
          </p>
          
          <div className="application-status__details">
            <dl>
              <dt>Application ID:</dt>
              <dd>{applicationId}</dd>
              <dt>Applicant:</dt>
              <dd>{application.applicantName}</dd>
              <dt>Documents:</dt>
              <dd>{application.documentInventory?.length || 0} uploaded</dd>
            </dl>
          </div>

          {submitError && <ErrorMessage error={submitError} title="Submission failed" />}

          <div className="application-status__actions">
            <Button onClick={handleSubmit} isLoading={isSubmitting} fullWidth>
              Submit Application
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  // Render processing status
  return (
    <Card title="Application Status">
      <div className="application-status">
        <div className="application-status__current">
          <StatusBadge status={application?.status || Status.PENDING} />
          <p className="application-status__id">Application ID: {applicationId}</p>
        </div>

        <div className="application-status__details">
          <dl>
            <dt>Applicant:</dt>
            <dd>{application?.applicantName}</dd>
            <dt>Status:</dt>
            <dd>{application?.status}</dd>
            <dt>Documents:</dt>
            <dd>{application?.documentInventory?.length || 0} documents</dd>
          </dl>
        </div>

        {!isTerminal && (
          <div className="application-status__progress">
            <LoadingSpinner size="md" label="Processing application..." />
            <p className="application-status__message">
              Your application is being processed. This may take a few moments.
            </p>
          </div>
        )}

        {isTerminal && (
          <div className="application-status__actions">
            <Button onClick={handleViewDecision} variant="primary" fullWidth>
              View Decision
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * Status badge component with color coding.
 */
function StatusBadge({ status }: { status: Status }) {
  const statusMap: Record<Status, { label: string; className: string }> = {
    [Status.PENDING]: { label: 'Pending', className: 'status-badge--pending' },
    [Status.PROCESSING]: { label: 'Processing', className: 'status-badge--processing' },
    [Status.COMPLETED]: { label: 'Completed', className: 'status-badge--completed' },
    [Status.FAILED]: { label: 'Failed', className: 'status-badge--failed' },
    [Status.MANUAL_REVIEW]: { label: 'Manual Review', className: 'status-badge--review' },
  };

  const config = statusMap[status] || { label: status, className: '' };

  return (
    <span className={`status-badge ${config.className}`} role="status">
      {config.label}
    </span>
  );
}
