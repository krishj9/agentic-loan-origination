/**
 * Login page with Cognito Hosted UI redirect.
 */

import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button, Card, LoadingSpinner } from '../components/ui';

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/';

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  const handleLogin = async () => {
    try {
      await login();
    } catch (error) {
      console.error('[LoginPage] Login failed:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="login-page">
        <LoadingSpinner size="lg" label="Checking authentication..." />
      </div>
    );
  }

  return (
    <div className="login-page">
      <Card title="Sign In">
        <div className="login-page__content">
          <p className="login-page__message">
            Sign in with your Cognito account to access the Loan Origination System.
          </p>
          <Button onClick={handleLogin} variant="primary" fullWidth>
            Sign In with Cognito
          </Button>
        </div>
      </Card>
    </div>
  );
}
