/**
 * Error message component with optional retry action.
 */

import { ApiClientError } from '../../api/client';

interface ErrorMessageProps {
  error: Error | ApiClientError | null;
  onRetry?: () => void;
  title?: string;
}

export function ErrorMessage({ error, onRetry, title = 'Error' }: ErrorMessageProps) {
  if (!error) return null;

  const isApiError = error instanceof ApiClientError;
  const message = isApiError ? error.detail : error.message;
  const status = isApiError ? error.status : undefined;

  return (
    <div className="error-message" role="alert">
      <div className="error-message__content">
        <h4 className="error-message__title">{title}</h4>
        <p className="error-message__text">{message}</p>
        {status && <p className="error-message__status">Status: {status}</p>}
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn btn--secondary" type="button">
          Retry
        </button>
      )}
    </div>
  );
}
