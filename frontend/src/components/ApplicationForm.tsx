/**
 * Application intake form with validation.
 * Submits POST /applications to create a new loan application.
 */

import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { useCreateApplication } from '../hooks/useApi';
import { Button, Input, Card, ErrorMessage } from './ui';
import type { CreateApplicationRequest } from '../types';

interface FormData {
  applicantName: string;
  annualIncome: string;
  requestedLoanAmount: string;
  debtUtilization: string;
}

export function ApplicationForm() {
  const navigate = useNavigate();
  const { mutate: createApplication, isPending, error } = useCreateApplication();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      applicantName: '',
      annualIncome: '',
      requestedLoanAmount: '',
      debtUtilization: '',
    },
  });

  const onSubmit = (data: FormData) => {
    const request: CreateApplicationRequest = {
      applicantName: data.applicantName,
      annualIncome: data.annualIncome,
      requestedLoanAmount: data.requestedLoanAmount,
      debtUtilization: data.debtUtilization,
    };

    createApplication(request, {
      onSuccess: (response) => {
        console.log('[ApplicationForm] Created application:', response.applicationId);
        // Navigate to document upload with the new application ID
        navigate(`/applications/${response.applicationId}/upload`);
      },
    });
  };

  return (
    <Card title="New Loan Application">
      <form onSubmit={handleSubmit(onSubmit)} className="application-form">
        <Input
          label="Applicant Name"
          {...register('applicantName', {
            required: 'Applicant name is required',
            minLength: { value: 2, message: 'Name must be at least 2 characters' },
          })}
          error={errors.applicantName?.message}
          placeholder="Jane Smith"
          required
        />

        <Input
          label="Annual Income (USD)"
          type="number"
          step="0.01"
          {...register('annualIncome', {
            required: 'Annual income is required',
            min: { value: 0, message: 'Income must be positive' },
            validate: (value) => {
              const num = parseFloat(value);
              return !isNaN(num) && num > 0 || 'Please enter a valid income';
            },
          })}
          error={errors.annualIncome?.message}
          placeholder="85000.00"
          helperText="Enter your total annual gross income"
          required
        />

        <Input
          label="Requested Loan Amount (USD)"
          type="number"
          step="0.01"
          {...register('requestedLoanAmount', {
            required: 'Loan amount is required',
            min: { value: 1000, message: 'Minimum loan amount is $1,000' },
            max: { value: 100000, message: 'Maximum loan amount is $100,000' },
          })}
          error={errors.requestedLoanAmount?.message}
          placeholder="20000.00"
          helperText="Between $1,000 and $100,000"
          required
        />

        <Input
          label="Debt Utilization Ratio"
          type="number"
          step="0.01"
          {...register('debtUtilization', {
            required: 'Debt utilization is required',
            min: { value: 0, message: 'Utilization must be between 0 and 1' },
            max: { value: 1, message: 'Utilization must be between 0 and 1' },
          })}
          error={errors.debtUtilization?.message}
          placeholder="0.25"
          helperText="Ratio of debt to available credit (0.25 = 25%)"
          required
        />

        {error && <ErrorMessage error={error} title="Failed to create application" />}

        <div className="application-form__actions">
          <Button type="submit" isLoading={isPending} fullWidth>
            Create Application
          </Button>
        </div>
      </form>
    </Card>
  );
}
