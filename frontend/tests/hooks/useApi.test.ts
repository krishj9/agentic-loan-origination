/**
 * Tests for API hooks using React Query.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import {
  useCreateApplication,
  useUploadDocument,
  useSubmitApplication,
  useApplication,
  useDecision,
  isTerminalStatus,
} from '../../src/hooks/useApi';
import { AllTheProviders } from '../../src/test/utils';
import { ApplicationStatus, DecisionOutcome, RiskProfile } from '../../src/types';

// Mock server
const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

const baseUrl = 'http://localhost:8000';

describe('useCreateApplication', () => {
  it('should create an application successfully', async () => {
    const mockResponse = {
      applicationId: 'app-123',
      status: ApplicationStatus.PENDING,
    };

    server.use(
      http.post(`${baseUrl}/applications`, () => {
        return HttpResponse.json(mockResponse);
      })
    );

    const { result } = renderHook(() => useCreateApplication(), {
      wrapper: AllTheProviders,
    });

    result.current.mutate({
      applicantName: 'John Doe',
      annualIncome: '80000',
      requestedLoanAmount: '20000',
      debtUtilization: '0.25',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockResponse);
  });

  it('should handle create application error', async () => {
    server.use(
      http.post(`${baseUrl}/applications`, () => {
        return HttpResponse.json(
          { detail: 'Validation error' },
          { status: 400 }
        );
      })
    );

    const { result } = renderHook(() => useCreateApplication(), {
      wrapper: AllTheProviders,
    });

    result.current.mutate({
      applicantName: '',
      annualIncome: '80000',
      requestedLoanAmount: '20000',
      debtUtilization: '0.25',
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeDefined();
  });
});

describe('useSubmitApplication', () => {
  it('should submit application successfully', async () => {
    const mockResponse = {
      applicationId: 'app-123',
      status: ApplicationStatus.PROCESSING,
      runtimeSessionId: 'session-456',
    };

    server.use(
      http.post(`${baseUrl}/applications/app-123/submit`, () => {
        return HttpResponse.json(mockResponse);
      })
    );

    const { result } = renderHook(() => useSubmitApplication(), {
      wrapper: AllTheProviders,
    });

    result.current.mutate('app-123');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockResponse);
  });
});

describe('useApplication', () => {
  it('should fetch application details', async () => {
    const mockApplication = {
      applicationId: 'app-123',
      userId: 'user-456',
      applicantName: 'John Doe',
      annualIncome: '80000',
      requestedLoanAmount: '20000',
      debtUtilization: '0.25',
      status: ApplicationStatus.PENDING,
      documentInventory: [],
    };

    server.use(
      http.get(`${baseUrl}/applications/app-123`, () => {
        return HttpResponse.json(mockApplication);
      })
    );

    const { result } = renderHook(() => useApplication('app-123'), {
      wrapper: AllTheProviders,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockApplication);
  });

  it('should not fetch when applicationId is null', () => {
    const { result } = renderHook(() => useApplication(null), {
      wrapper: AllTheProviders,
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.isLoading).toBe(false);
  });
});

describe('useDecision', () => {
  it('should fetch decision details', async () => {
    const mockDecision = {
      applicationId: 'app-123',
      outcome: DecisionOutcome.APPROVE,
      riskProfile: RiskProfile.PRIME,
      creditScore: 750,
      rationale: 'Application approved based on strong credit profile.',
    };

    server.use(
      http.get(`${baseUrl}/applications/app-123/decision`, () => {
        return HttpResponse.json(mockDecision);
      })
    );

    const { result } = renderHook(() => useDecision('app-123'), {
      wrapper: AllTheProviders,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockDecision);
  });
});

describe('isTerminalStatus', () => {
  it('should identify terminal statuses', () => {
    expect(isTerminalStatus(ApplicationStatus.COMPLETED)).toBe(true);
    expect(isTerminalStatus(ApplicationStatus.FAILED)).toBe(true);
    expect(isTerminalStatus(ApplicationStatus.MANUAL_REVIEW)).toBe(true);
  });

  it('should identify non-terminal statuses', () => {
    expect(isTerminalStatus(ApplicationStatus.PENDING)).toBe(false);
    expect(isTerminalStatus(ApplicationStatus.PROCESSING)).toBe(false);
  });
});
