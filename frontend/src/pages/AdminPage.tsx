/**
 * Admin/Operator page with read-only config and log pointers.
 * Minimal implementation for v1 as per P5-T10.
 */

import { Card } from '../components/ui';

export function AdminPage() {
  const cloudWatchUrl = import.meta.env.VITE_CLOUDWATCH_LOGS_URL || 'https://console.aws.amazon.com/cloudwatch';

  return (
    <div className="admin-page">
      <h1>Operations Dashboard</h1>
      
      <Card title="System Monitoring">
        <p>Monitor application logs and metrics in CloudWatch:</p>
        <ul className="admin-page__links">
          <li>
            <a href={cloudWatchUrl} target="_blank" rel="noopener noreferrer">
              CloudWatch Logs
            </a>
          </li>
        </ul>
      </Card>

      <Card title="Configuration">
        <p>System configuration is managed via Terraform and environment variables.</p>
        <dl className="admin-page__config">
          <dt>API Base URL:</dt>
          <dd><code>{import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</code></dd>
          <dt>AWS Region:</dt>
          <dd><code>{import.meta.env.VITE_AWS_REGION || 'N/A'}</code></dd>
          <dt>Environment:</dt>
          <dd><code>{import.meta.env.MODE}</code></dd>
        </dl>
      </Card>

      <Card title="Evaluation Results">
        <p>
          Golden-case replay results and drift detection metrics are available in CloudWatch Logs
          and the evaluation output directory.
        </p>
      </Card>
    </div>
  );
}
