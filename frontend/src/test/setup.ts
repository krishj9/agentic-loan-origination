/**
 * Test setup file for vitest.
 * Configures testing environment and global mocks.
 */

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock environment variables
vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
vi.stubEnv('VITE_AWS_REGION', 'us-east-1');
vi.stubEnv('VITE_COGNITO_USER_POOL_ID', 'us-east-1_test');
vi.stubEnv('VITE_COGNITO_USER_POOL_CLIENT_ID', 'test-client-id');
vi.stubEnv('VITE_COGNITO_OAUTH_DOMAIN', 'test.auth.us-east-1.amazoncognito.com');

// Mock window.matchMedia for responsive tests
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
