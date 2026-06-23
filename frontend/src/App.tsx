/**
 * Main App component with routing, auth, and React Query setup.
 */

import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { setTokenProvider } from './api/client';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { AdminPage } from './pages/AdminPage';
import { ApplicationForm } from './components/ApplicationForm';
import { DocumentUpload } from './components/DocumentUpload';
import { ApplicationStatus } from './components/ApplicationStatus';
import { DecisionView } from './components/DecisionView';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5000,
    },
  },
});

/**
 * Token provider setup component.
 * Must be inside AuthProvider to access useAuth.
 */
function TokenProviderSetup({ children }: { children: React.ReactNode }) {
  const { getAccessToken } = useAuth();

  useEffect(() => {
    setTokenProvider(getAccessToken);
  }, [getAccessToken]);

  return <>{children}</>;
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TokenProviderSetup>
            <BrowserRouter>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                
                <Route element={<Layout />}>
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute>
                        <HomePage />
                      </ProtectedRoute>
                    }
                  />
                  
                  <Route
                    path="/applications/new"
                    element={
                      <ProtectedRoute requiredRole="LoanOfficer">
                        <ApplicationForm />
                      </ProtectedRoute>
                    }
                  />
                  
                  <Route
                    path="/applications/:applicationId/upload"
                    element={
                      <ProtectedRoute requiredRole="LoanOfficer">
                        <DocumentUpload />
                      </ProtectedRoute>
                    }
                  />
                  
                  <Route
                    path="/applications/:applicationId/submit"
                    element={
                      <ProtectedRoute requiredRole="LoanOfficer">
                        <ApplicationStatus />
                      </ProtectedRoute>
                    }
                  />
                  
                  <Route
                    path="/applications/:applicationId/decision"
                    element={
                      <ProtectedRoute requiredRole="LoanOfficer">
                        <DecisionView />
                      </ProtectedRoute>
                    }
                  />
                  
                  <Route
                    path="/admin"
                    element={
                      <ProtectedRoute requiredRole="Operator">
                        <AdminPage />
                      </ProtectedRoute>
                    }
                  />
                  
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </TokenProviderSetup>
        </AuthProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
