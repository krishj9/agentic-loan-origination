/**
 * Input component with label, error state, and accessibility.
 */

import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className = '', id, required, ...props }, ref) => {
    const inputId = id || `input-${label.replace(/\s+/g, '-').toLowerCase()}`;
    const errorId = error ? `${inputId}-error` : undefined;
    const helperId = helperText ? `${inputId}-helper` : undefined;

    return (
      <div className={`input-field ${className}`}>
        <label htmlFor={inputId} className="input-field__label">
          {label}
          {required && <span className="input-field__required" aria-label="required">*</span>}
        </label>
        <input
          ref={ref}
          id={inputId}
          className={`input-field__input ${error ? 'input-field__input--error' : ''}`}
          aria-invalid={!!error}
          aria-describedby={[errorId, helperId].filter(Boolean).join(' ') || undefined}
          required={required}
          {...props}
        />
        {helperText && !error && (
          <span id={helperId} className="input-field__helper">
            {helperText}
          </span>
        )}
        {error && (
          <span id={errorId} className="input-field__error" role="alert">
            {error}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
