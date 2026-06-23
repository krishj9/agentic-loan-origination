/**
 * Custom hooks for API operations using React Query.
 * Every API call is wrapped in a hook with loading/error/data state.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiClientError } from '../api/client';
import type {
  CreateApplicationRequest,
  CreateApplicationResponse,
  UploadDocumentResponse,
  SubmitApplicationResponse,
  GetApplicationResponse,
  GetDecisionResponse,
  DocumentType,
} from '../types';

/**
 * Query keys for React Query cache management.
 */
export const queryKeys = {
  application: (id: string) => ['application', id] as const,
  decision: (id: string) => ['decision', id] as const,
  health: () => ['health'] as const,
};

/**
 * Hook to create a new application.
 */
export function useCreateApplication() {
  const queryClient = useQueryClient();

  return useMutation<CreateApplicationResponse, ApiClientError, CreateApplicationRequest>({
    mutationFn: (data) => apiClient.createApplication(data),
    onSuccess: (data) => {
      // Invalidate and prefetch the new application
      queryClient.invalidateQueries({ queryKey: ['application'] });
      queryClient.prefetchQuery({
        queryKey: queryKeys.application(data.applicationId),
        queryFn: () => apiClient.getApplication(data.applicationId),
      });
    },
  });
}

/**
 * Hook to request document upload presigned URL.
 */
export function useRequestDocumentUpload() {
  return useMutation<
    UploadDocumentResponse,
    ApiClientError,
    { applicationId: string; documentType: DocumentType }
  >({
    mutationFn: ({ applicationId, documentType }) =>
      apiClient.requestDocumentUpload(applicationId, documentType),
  });
}

/**
 * Hook to upload document to S3.
 */
export function useUploadDocumentToS3() {
  const queryClient = useQueryClient();

  return useMutation<void, ApiClientError, { presignedUrl: string; file: File; applicationId: string }>({
    mutationFn: ({ presignedUrl, file }) => apiClient.uploadDocumentToS3(presignedUrl, file),
    onSuccess: (_, variables) => {
      // Invalidate application query to refresh document inventory
      queryClient.invalidateQueries({ queryKey: queryKeys.application(variables.applicationId) });
    },
  });
}

/**
 * Combined hook for document upload flow (request URL + upload to S3).
 */
export function useUploadDocument() {
  const requestUpload = useRequestDocumentUpload();
  const uploadToS3 = useUploadDocumentToS3();

  const uploadDocument = async (applicationId: string, documentType: DocumentType, file: File) => {
    // Step 1: Request presigned URL
    const uploadResponse = await requestUpload.mutateAsync({ applicationId, documentType });

    // Step 2: Upload to S3
    await uploadToS3.mutateAsync({
      presignedUrl: uploadResponse.presignedUrl,
      file,
      applicationId,
    });

    return uploadResponse;
  };

  return {
    uploadDocument,
    isLoading: requestUpload.isPending || uploadToS3.isPending,
    error: requestUpload.error || uploadToS3.error,
    reset: () => {
      requestUpload.reset();
      uploadToS3.reset();
    },
  };
}

/**
 * Hook to submit application for processing.
 */
export function useSubmitApplication() {
  const queryClient = useQueryClient();

  return useMutation<SubmitApplicationResponse, ApiClientError, string>({
    mutationFn: (applicationId) => apiClient.submitApplication(applicationId),
    onSuccess: (_, applicationId) => {
      // Invalidate application to refresh status
      queryClient.invalidateQueries({ queryKey: queryKeys.application(applicationId) });
    },
  });
}

/**
 * Hook to get application details with optional polling.
 */
export function useApplication(
  applicationId: string | null,
  options?: {
    refetchInterval?: number | false;
    enabled?: boolean;
  }
) {
  return useQuery<GetApplicationResponse, ApiClientError>({
    queryKey: queryKeys.application(applicationId!),
    queryFn: () => apiClient.getApplication(applicationId!),
    enabled: !!applicationId && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval,
    refetchIntervalInBackground: false,
  });
}

/**
 * Hook to get application decision.
 */
export function useDecision(applicationId: string | null, options?: { enabled?: boolean }) {
  return useQuery<GetDecisionResponse, ApiClientError>({
    queryKey: queryKeys.decision(applicationId!),
    queryFn: () => apiClient.getDecision(applicationId!),
    enabled: !!applicationId && (options?.enabled ?? true),
    retry: 1, // Decision may not be available immediately
  });
}

/**
 * Hook for health check.
 */
export function useHealthCheck() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: () => apiClient.healthCheck(),
    refetchInterval: 30000, // Check every 30 seconds
    retry: false,
  });
}

/**
 * Helper to determine if application is in terminal state.
 */
export function isTerminalStatus(status: string): boolean {
  return ['COMPLETED', 'FAILED', 'MANUAL_REVIEW'].includes(status);
}
