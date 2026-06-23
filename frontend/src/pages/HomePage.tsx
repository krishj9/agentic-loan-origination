/**
 * Home page with navigation to key features.
 */

import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, Button } from '../components/ui';

export function HomePage() {
  const { user } = useAuth();

  return (
    <div className="home-page">
      <div className="home-page__hero">
        <h1>Welcome to Loan Origination System</h1>
        <p>
          Agentic loan processing powered by LangGraph, Amazon Bedrock, and AWS infrastructure.
        </p>
      </div>

      <div className="home-page__cards">
        <Card title="New Application">
          <p>Start a new loan application with applicant information and document upload.</p>
          <Link to="/applications/new">
            <Button variant="primary" fullWidth>
              Create Application
            </Button>
          </Link>
        </Card>

        {user?.groups.includes('LoanOfficer') && (
          <Card title="Loan Officer Tools">
            <p>Review applications, track status, and view decisions.</p>
            <ul>
              <li>Submit applications for processing</li>
              <li>Monitor real-time status updates</li>
              <li>Download decision artifacts</li>
            </ul>
          </Card>
        )}

        {user?.groups.includes('Operator') && (
          <Card title="Operations">
            <Link to="/admin">
              <Button variant="secondary" fullWidth>
                Admin Dashboard
              </Button>
            </Link>
          </Card>
        )}
      </div>

      <div className="home-page__info">
        <h2>System Features</h2>
        <ul>
          <li>AI-powered document extraction using LlamaParse</li>
          <li>Deterministic risk assessment with explainable decisions</li>
          <li>Rule-based compliance checking</li>
          <li>Real-time application status tracking</li>
          <li>Structured decision artifacts (JSON + PDF)</li>
        </ul>
      </div>
    </div>
  );
}
