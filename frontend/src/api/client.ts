/**
 * Typed API client for backend communication.
 * All API calls go through this centralized client with auth token injection.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { getApiConfig } from '../config/api';
import type {
  ApiError,
  CreateApplicationRequest,
  CreateApplicationResponse,
  UploadDocumentResponse,
  SubmitApplicationResponse,
  GetApplicationResponse,
  GetDecisionResponse,
  DocumentType,
} from '../types';

const apiConfig = getApiConfig();

/**
 * Axios instance with default config.
 */
const axiosInstance: AxiosInstance = axios.create({
  baseURL: apiConfig.baseUrl,
  timeout: apiConfig.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Normalized error structure for API failures.
 */
export class ApiClientError extends Error {
  public readonly status: number;
  public readonly detail: string;
  public readonly timestamp: string;

  constructor(error: AxiosError<ApiError>) {
    const detail = error.response?.data?.detail || error.message || 'Unknown API error';
    const status = error.response?.status || 500;
    const timestamp = error.response?.data?.timestamp || new Date().toISOString();

    super(detail);
    this.name = 'ApiClientError';
    this.status = status;
    this.detail = detail;
    this.timestamp = timestamp;

    // Structured logging for debugging
    console.error('[ApiClient] Error:', {
      status,
      detail,
      timestamp,
      url: error.config?.url,
      method: error.config?.method,
    });
  }
}

/**
 * Request interceptor to inject auth token.
 * Token provider function is set externally after AuthContext is available.
 */
let tokenProvider: (() => Promise<string | null>) | null = null;

export function setTokenProvider(provider: () => Promise<string | null>) {
  tokenProvider = provider;
}

axiosInstance.interceptors.request.use(
  async (config) => {
    if (tokenProvider) {
      const token = await tokenProvider();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Response interceptor to normalize errors.
 */
axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    throw new ApiClientError(error);
  }
);

/**
 * Typed API client methods.
 */
export const apiClient = {
  /**
   * Create a new loan application.
   * POST /applications
   */
  async createApplication(
    data: CreateApplicationRequest
  ): Promise<CreateApplicationResponse> {
    const response = await axiosInstance.post<CreateApplicationResponse>(
      '/applications',
      data
    );
    return response.data;
  },

  /**
   * Request presigned URL for document upload.
   * POST /applications/{applicationId}/documents
   */
  async requestDocumentUpload(
    applicationId: string,
    documentType: DocumentType
  ): Promise<UploadDocumentResponse> {
    const response = await axiosInstance.post<UploadDocumentResponse>(
      `/applications/${applicationId}/documents`,
      { documentType }
    );
    return response.data;
  },

  /**
   * Upload document to S3 using presigned URL.
   * Direct PUT to S3, not to backend API.
   */
  async uploadDocumentToS3(presignedUrl: string, file: File): Promise<void> {
    await axios.put(presignedUrl, file, {
      headers: {
        'Content-Type': file.type,
      },
      timeout: apiConfig.timeout * 2, // Longer timeout for uploads
    });
  },

  /**
   * Submit application for processing.
   * POST /applications/{applicationId}/submit
   */
  async submitApplication(applicationId: string): Promise<SubmitApplicationResponse> {
    const response = await axiosInstance.post<SubmitApplicationResponse>(
      `/applications/${applicationId}/submit`
    );
    return response.data;
  },

  /**
   * Get application status and details.
   * GET /applications/{applicationId}
   */
  async getApplication(applicationId: string): Promise<GetApplicationResponse> {
    const response = await axiosInstance.get<GetApplicationResponse>(
      `/applications/${applicationId}`
    );
    return response.data;
  },

  /**
   * Get application decision.
   * GET /applications/{applicationId}/decision
   */
  async getDecision(applicationId: string): Promise<GetDecisionResponse> {
    const response = await axiosInstance.get<GetDecisionResponse>(
      `/applications/${applicationId}/decision`
    );
    return response.data;
  },

  /**
   * Health check endpoint.
   * GET /health
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await axiosInstance.get<{ status: string }>('/health');
    return response.data;
  },
};
