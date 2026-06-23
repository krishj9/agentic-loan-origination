/**
 * Playwright E2E tests — P6-T9
 *
 * Covers the complete create-to-decision browser flow:
 *   1. Login page renders correctly.
 *   2. Unauthenticated users are redirected to /login.
 *   3. Application intake form validation.
 *   4. Application form submission creates an application.
 *   5. Document upload step renders after creation.
 *   6. Decision view renders expected outcome.
 *
 * Offline / no-real-AWS mode
 * --------------------------
 * These tests use Playwright's route interception (``page.route``) to mock all
 * API calls, so no running backend or AWS credentials are required.  This keeps
 * the tests fast and deterministic in CI.
 *
 * The mocked API responses match the shapes defined in the backend OpenAPI spec
 * and ``shared/schemas``.
 *
 * Stable selectors
 * ----------------
 * Tests use ``data-testid`` attributes (ARIA roles and visible text as fallback)
 * to minimise coupling to CSS classes or DOM structure.
 */

import { test, expect, Page } from '@playwright/test';

// ── Constants ──────────────────────────────────────────────────────────────────

const GOLDEN_APPLICATION_ID = 'app_e2e_golden_001';
const BASE = '/';

// ── Mock API helpers ───────────────────────────────────────────────────────────

/**
 * Install route intercepts that mock the backend REST API.
 *
 * All responses are deterministic and match the golden PRIME applicant scenario.
 */
async function installApiMocks(page: Page): Promise<void> {
  // POST /applications → 201 Created
  await page.route('**/applications', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          applicationId: GOLDEN_APPLICATION_ID,
          applicantName: 'E2E Test User',
          annualIncome: '90000.00',
          requestedLoanAmount: '20000.00',
          debtUtilization: '0.20',
          status: 'PENDING',
          documentCount: 0,
          documentInventory: [],
          createdAt: new Date().toISOString(),
        }),
      });
    } else {
      await route.continue();
    }
  });

  // POST /applications/:id/documents → presigned URL
  await page.route(`**/applications/${GOLDEN_APPLICATION_ID}/documents`, async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          documentId: `doc_${Date.now()}`,
          uploadUrl: 'https://s3.example.com/presigned-e2e-upload',
        }),
      });
    } else {
      await route.continue();
    }
  });

  // POST /applications/:id/submit → 202 Accepted
  await page.route(`**/applications/${GOLDEN_APPLICATION_ID}/submit`, async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          applicationId: GOLDEN_APPLICATION_ID,
          status: 'PROCESSING',
          message: 'Application submitted for processing.',
          runtimeSessionId: 'local-e2e-session-001',
        }),
      });
    } else {
      await route.continue();
    }
  });

  // GET /applications/:id → COMPLETED with decision
  await page.route(`**/applications/${GOLDEN_APPLICATION_ID}`, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          applicationId: GOLDEN_APPLICATION_ID,
          applicantName: 'E2E Test User',
          annualIncome: '90000.00',
          requestedLoanAmount: '20000.00',
          debtUtilization: '0.20',
          status: 'COMPLETED',
          documentCount: 2,
          documentInventory: [],
          decision: {
            applicationId: GOLDEN_APPLICATION_ID,
            outcome: 'APPROVE',
            rationale: 'PRIME applicant; all checks passed.',
            decidedAt: new Date().toISOString(),
          },
          riskResponse: {
            applicantId: GOLDEN_APPLICATION_ID,
            riskProfile: 'PRIME',
            creditScore: 752,
          },
        }),
      });
    } else {
      await route.continue();
    }
  });

  // GET /applications/:id/decision → structured decision
  await page.route(`**/applications/${GOLDEN_APPLICATION_ID}/decision`, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          applicationId: GOLDEN_APPLICATION_ID,
          outcome: 'APPROVE',
          rationale: 'Annual income HIGH ($90,000), debt utilisation LOW (20%). Assigned PRIME band (score range 720–800). Deterministic credit score: 752.',
          decidedAt: new Date().toISOString(),
          riskProfile: 'PRIME',
          creditScore: 752,
          complianceFlags: [],
          artifactJsonS3Key: `archive/${GOLDEN_APPLICATION_ID}/decision.json`,
          artifactPdfS3Key: `archive/${GOLDEN_APPLICATION_ID}/decision.pdf`,
        }),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Mock the auth context so tests bypass the real Cognito login flow.
 * Injects a fake auth token into localStorage so ProtectedRoute passes.
 */
async function injectAuthToken(page: Page): Promise<void> {
  await page.addInitScript(() => {
    // Seed a mock auth token that the app's AuthContext can pick up.
    // The exact key depends on the Amplify/auth library configuration.
    const mockSession = {
      sub: 'sub-e2e-test',
      username: 'e2e.loan.officer',
      groups: ['LoanOfficer'],
      idToken: 'mock-id-token-for-e2e',
      accessToken: 'mock-access-token-for-e2e',
    };
    window.localStorage.setItem('e2e_mock_auth', JSON.stringify(mockSession));
    // Patch fetch so Authorization header is always set (belt + suspenders)
    const originalFetch = window.fetch;
    window.fetch = (input, init = {}) => {
      const headers = new Headers(init.headers);
      if (!headers.has('Authorization')) {
        headers.set('Authorization', 'Bearer mock-access-token-for-e2e');
      }
      return originalFetch(input, { ...init, headers });
    };
  });
}

// ── Test suites ────────────────────────────────────────────────────────────────

test.describe('Login Page', () => {
  test('renders login page at /login', async ({ page }) => {
    await page.goto('/login');
    // The login page should have a heading or a sign-in element
    await expect(page).toHaveURL(/\/login/);
    // Check page has some content (heading, button, or form)
    const body = page.locator('body');
    await expect(body).not.toBeEmpty();
  });

  test('unauthenticated visit to / redirects to /login', async ({ page }) => {
    // Clear any existing auth state
    await page.context().clearCookies();
    await page.evaluate(() => window.localStorage.clear());
    await page.goto('/');
    // Should redirect to login (the ProtectedRoute redirects unauthenticated users)
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe('Application Form', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    await injectAuthToken(page);
    await page.goto('/applications/new');
  });

  test('form renders all required input fields', async ({ page }) => {
    // These labels are defined in ApplicationForm.tsx
    await expect(page.getByLabel('Applicant Name')).toBeVisible();
    await expect(page.getByLabel('Annual Income (USD)')).toBeVisible();
    await expect(page.getByLabel('Requested Loan Amount (USD)')).toBeVisible();
    await expect(page.getByLabel('Debt Utilization Ratio')).toBeVisible();
  });

  test('submit button is visible', async ({ page }) => {
    const submitBtn = page.getByRole('button', { name: /create application/i });
    await expect(submitBtn).toBeVisible();
  });

  test('shows validation error when applicant name is empty', async ({ page }) => {
    // Click submit without filling the form
    await page.getByRole('button', { name: /create application/i }).click();
    // Validation message should appear
    await expect(page.getByText(/applicant name is required/i)).toBeVisible();
  });

  test('shows validation error for invalid income', async ({ page }) => {
    await page.getByLabel('Applicant Name').fill('E2E Test User');
    await page.getByLabel('Annual Income (USD)').fill('-100');
    await page.getByLabel('Requested Loan Amount (USD)').fill('20000');
    await page.getByLabel('Debt Utilization Ratio').fill('0.25');
    await page.getByRole('button', { name: /create application/i }).click();
    // Either form validation or API error should be shown
    const errorText = page.getByText(/income must be positive|valid income/i);
    await expect(errorText).toBeVisible();
  });

  test('successful submission navigates to document upload', async ({ page }) => {
    await page.getByLabel('Applicant Name').fill('E2E Test User');
    await page.getByLabel('Annual Income (USD)').fill('90000');
    await page.getByLabel('Requested Loan Amount (USD)').fill('20000');
    await page.getByLabel('Debt Utilization Ratio').fill('0.20');

    await page.getByRole('button', { name: /create application/i }).click();

    // After success the app navigates to the upload step
    await expect(page).toHaveURL(
      new RegExp(`/applications/${GOLDEN_APPLICATION_ID}/upload`),
      { timeout: 10_000 }
    );
  });
});

test.describe('Decision View', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    await injectAuthToken(page);
    // Navigate directly to the decision page for the golden application
    await page.goto(`/applications/${GOLDEN_APPLICATION_ID}/decision`);
  });

  test('renders decision page without crashing', async ({ page }) => {
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('displays APPROVE outcome for PRIME golden applicant', async ({ page }) => {
    // The decision view should display the outcome text
    const approveText = page.getByText(/approve/i).first();
    await expect(approveText).toBeVisible({ timeout: 10_000 });
  });

  test('displays PRIME risk profile', async ({ page }) => {
    const primeText = page.getByText(/prime/i).first();
    await expect(primeText).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('Full Application Flow (E2E)', () => {
  /**
   * Golden path: new application → upload docs (simulated) → submit → decision.
   *
   * The API responses are fully mocked so no backend or AWS is needed.
   */
  test('create → navigate to upload → check decision page', async ({ page }) => {
    await installApiMocks(page);
    await injectAuthToken(page);

    // Step 1: Start at the new-application form
    await page.goto('/applications/new');
    await expect(page.getByLabel('Applicant Name')).toBeVisible();

    // Step 2: Fill and submit the form
    await page.getByLabel('Applicant Name').fill('E2E Golden Prime User');
    await page.getByLabel('Annual Income (USD)').fill('90000');
    await page.getByLabel('Requested Loan Amount (USD)').fill('20000');
    await page.getByLabel('Debt Utilization Ratio').fill('0.20');
    await page.getByRole('button', { name: /create application/i }).click();

    // Step 3: Should navigate to upload page
    await expect(page).toHaveURL(
      new RegExp(`/applications/${GOLDEN_APPLICATION_ID}/upload`),
      { timeout: 10_000 }
    );

    // Step 4: Navigate directly to decision (skipping real file upload)
    await page.goto(`/applications/${GOLDEN_APPLICATION_ID}/decision`);

    // Step 5: Decision page should display APPROVE outcome
    const outcome = page.getByText(/approve/i).first();
    await expect(outcome).toBeVisible({ timeout: 10_000 });
  });
});
