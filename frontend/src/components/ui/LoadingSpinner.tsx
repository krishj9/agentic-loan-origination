/**
 * Loading spinner component for async operations.
 */

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

export function LoadingSpinner({ size = 'md', label }: LoadingSpinnerProps) {
  const sizeClass = `spinner--${size}`;

  return (
    <div className="loading-spinner" role="status" aria-live="polite">
      <div className={`spinner ${sizeClass}`} aria-hidden="true"></div>
      {label && <span className="loading-spinner__label">{label}</span>}
      <span className="sr-only">Loading...</span>
    </div>
  );
}
