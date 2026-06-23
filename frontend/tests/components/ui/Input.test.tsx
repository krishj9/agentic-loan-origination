/**
 * Tests for Input component.
 */

import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '../../../src/components/ui/Input';

describe('Input', () => {
  it('should render with label', () => {
    render(<Input label="Name" />);
    
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
  });

  it('should show required indicator when required', () => {
    render(<Input label="Email" required />);
    
    expect(screen.getByLabelText(/email/i)).toBeRequired();
    expect(screen.getByText('*')).toBeInTheDocument();
  });

  it('should display helper text', () => {
    render(<Input label="Username" helperText="Choose a unique username" />);
    
    expect(screen.getByText('Choose a unique username')).toBeInTheDocument();
  });

  it('should display error message', () => {
    render(<Input label="Password" error="Password is required" />);
    
    const input = screen.getByLabelText('Password');
    expect(input).toHaveClass('input-field__input--error');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Password is required');
  });

  it('should hide helper text when error is present', () => {
    render(
      <Input
        label="Email"
        helperText="Enter your email"
        error="Invalid email"
      />
    );
    
    expect(screen.queryByText('Enter your email')).not.toBeInTheDocument();
    expect(screen.getByText('Invalid email')).toBeInTheDocument();
  });

  it('should handle user input', async () => {
    const user = userEvent.setup();
    render(<Input label="Name" />);
    
    const input = screen.getByLabelText('Name');
    await user.type(input, 'John Doe');
    
    expect(input).toHaveValue('John Doe');
  });

  it('should support different input types', () => {
    render(<Input label="Age" type="number" />);
    
    expect(screen.getByLabelText('Age')).toHaveAttribute('type', 'number');
  });

  it('should be accessible with proper ARIA attributes', () => {
    render(
      <Input
        label="Email"
        helperText="We'll never share your email"
        error="Email is required"
        required
      />
    );
    
    const input = screen.getByLabelText(/email/i);
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby');
  });
});
