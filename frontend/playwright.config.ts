import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E tests (P6-T9).
 *
 * Tests run against a locally-served dev build of the frontend.  When the
 * ``BASE_URL`` environment variable is set the tests can target any environment
 * (staging, production-read-only, etc.) without code changes.
 *
 * All flows run against a single Chromium browser to keep CI fast.  Add
 * Firefox/WebKit blocks here when cross-browser coverage is needed.
 *
 * Offline / no-real-AWS mode:
 *   The frontend app uses mock-service-worker (MSW) in test mode.  The E2E
 *   tests assert on the MSW-backed responses, not real backend calls.  The
 *   ``PLAYWRIGHT_USE_MOCKS`` env var is forwarded to the Vite dev server so
 *   the app bootstraps MSW automatically when tests run.
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts',

  /* Run tests in parallel within a file, sequentially across files. */
  fullyParallel: false,
  workers: 1,

  /* Retry failing tests once in CI to reduce flakiness. */
  retries: process.env.CI ? 1 : 0,

  /* Fail the suite immediately on any unexpected timeout. */
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },

  /* Reporter: concise list in CI, interactive HTML locally. */
  reporter: process.env.CI
    ? [['list'], ['json', { outputFile: 'test-results/playwright-results.json' }]]
    : [['html', { outputFolder: 'test-results/playwright-html' }]],

  use: {
    /* Target the locally running dev server (override with BASE_URL). */
    baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:5173',

    /* Forward the mock flag so the app enables MSW. */
    extraHTTPHeaders: {
      'X-Playwright-Test': 'true',
    },

    /* Capture screenshot + video only on failure. */
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /*
   * Start the Vite dev server automatically when running locally.
   * In CI the server is expected to be already running (started by the job).
   */
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: true,
        timeout: 60_000,
        env: {
          PLAYWRIGHT_USE_MOCKS: 'true',
          VITE_API_BASE_URL: 'http://localhost:8000',
        },
      },
});
