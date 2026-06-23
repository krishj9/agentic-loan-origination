/**
 * API configuration.
 */

export interface ApiConfig {
  baseUrl: string;
  timeout: number;
}

/**
 * Load API configuration from environment variables.
 */
export function getApiConfig(): ApiConfig {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const timeout = parseInt(import.meta.env.VITE_API_TIMEOUT || '30000', 10);

  return {
    baseUrl,
    timeout,
  };
}
