# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: loan_application_flow.spec.ts >> Application Form >> form renders all required input fields
- Location: tests/e2e/loan_application_flow.spec.ts:213:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByLabel('Applicant Name')
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for getByLabel('Applicant Name')

```

# Test source

```ts
  115 |             applicationId: GOLDEN_APPLICATION_ID,
  116 |             outcome: 'APPROVE',
  117 |             rationale: 'PRIME applicant; all checks passed.',
  118 |             decidedAt: new Date().toISOString(),
  119 |           },
  120 |           riskResponse: {
  121 |             applicantId: GOLDEN_APPLICATION_ID,
  122 |             riskProfile: 'PRIME',
  123 |             creditScore: 752,
  124 |           },
  125 |         }),
  126 |       });
  127 |     } else {
  128 |       await route.continue();
  129 |     }
  130 |   });
  131 | 
  132 |   // GET /applications/:id/decision → structured decision
  133 |   await page.route(`**/applications/${GOLDEN_APPLICATION_ID}/decision`, async (route) => {
  134 |     if (route.request().method() === 'GET') {
  135 |       await route.fulfill({
  136 |         status: 200,
  137 |         contentType: 'application/json',
  138 |         body: JSON.stringify({
  139 |           applicationId: GOLDEN_APPLICATION_ID,
  140 |           outcome: 'APPROVE',
  141 |           rationale: 'Annual income HIGH ($90,000), debt utilisation LOW (20%). Assigned PRIME band (score range 720–800). Deterministic credit score: 752.',
  142 |           decidedAt: new Date().toISOString(),
  143 |           riskProfile: 'PRIME',
  144 |           creditScore: 752,
  145 |           complianceFlags: [],
  146 |           artifactJsonS3Key: `archive/${GOLDEN_APPLICATION_ID}/decision.json`,
  147 |           artifactPdfS3Key: `archive/${GOLDEN_APPLICATION_ID}/decision.pdf`,
  148 |         }),
  149 |       });
  150 |     } else {
  151 |       await route.continue();
  152 |     }
  153 |   });
  154 | }
  155 | 
  156 | /**
  157 |  * Mock the auth context so tests bypass the real Cognito login flow.
  158 |  * Injects a fake auth token into localStorage so ProtectedRoute passes.
  159 |  */
  160 | async function injectAuthToken(page: Page): Promise<void> {
  161 |   await page.addInitScript(() => {
  162 |     // Seed a mock auth token that the app's AuthContext can pick up.
  163 |     // The exact key depends on the Amplify/auth library configuration.
  164 |     const mockSession = {
  165 |       sub: 'sub-e2e-test',
  166 |       username: 'e2e.loan.officer',
  167 |       groups: ['LoanOfficer'],
  168 |       idToken: 'mock-id-token-for-e2e',
  169 |       accessToken: 'mock-access-token-for-e2e',
  170 |     };
  171 |     window.localStorage.setItem('e2e_mock_auth', JSON.stringify(mockSession));
  172 |     // Patch fetch so Authorization header is always set (belt + suspenders)
  173 |     const originalFetch = window.fetch;
  174 |     window.fetch = (input, init = {}) => {
  175 |       const headers = new Headers(init.headers);
  176 |       if (!headers.has('Authorization')) {
  177 |         headers.set('Authorization', 'Bearer mock-access-token-for-e2e');
  178 |       }
  179 |       return originalFetch(input, { ...init, headers });
  180 |     };
  181 |   });
  182 | }
  183 | 
  184 | // ── Test suites ────────────────────────────────────────────────────────────────
  185 | 
  186 | test.describe('Login Page', () => {
  187 |   test('renders login page at /login', async ({ page }) => {
  188 |     await page.goto('/login');
  189 |     // The login page should have a heading or a sign-in element
  190 |     await expect(page).toHaveURL(/\/login/);
  191 |     // Check page has some content (heading, button, or form)
  192 |     const body = page.locator('body');
  193 |     await expect(body).not.toBeEmpty();
  194 |   });
  195 | 
  196 |   test('unauthenticated visit to / redirects to /login', async ({ page }) => {
  197 |     // Clear any existing auth state
  198 |     await page.context().clearCookies();
  199 |     await page.evaluate(() => window.localStorage.clear());
  200 |     await page.goto('/');
  201 |     // Should redirect to login (the ProtectedRoute redirects unauthenticated users)
  202 |     await expect(page).toHaveURL(/\/login/);
  203 |   });
  204 | });
  205 | 
  206 | test.describe('Application Form', () => {
  207 |   test.beforeEach(async ({ page }) => {
  208 |     await installApiMocks(page);
  209 |     await injectAuthToken(page);
  210 |     await page.goto('/applications/new');
  211 |   });
  212 | 
  213 |   test('form renders all required input fields', async ({ page }) => {
  214 |     // These labels are defined in ApplicationForm.tsx
> 215 |     await expect(page.getByLabel('Applicant Name')).toBeVisible();
      |                                                     ^ Error: expect(locator).toBeVisible() failed
  216 |     await expect(page.getByLabel('Annual Income (USD)')).toBeVisible();
  217 |     await expect(page.getByLabel('Requested Loan Amount (USD)')).toBeVisible();
  218 |     await expect(page.getByLabel('Debt Utilization Ratio')).toBeVisible();
  219 |   });
  220 | 
  221 |   test('submit button is visible', async ({ page }) => {
  222 |     const submitBtn = page.getByRole('button', { name: /create application/i });
  223 |     await expect(submitBtn).toBeVisible();
  224 |   });
  225 | 
  226 |   test('shows validation error when applicant name is empty', async ({ page }) => {
  227 |     // Click submit without filling the form
  228 |     await page.getByRole('button', { name: /create application/i }).click();
  229 |     // Validation message should appear
  230 |     await expect(page.getByText(/applicant name is required/i)).toBeVisible();
  231 |   });
  232 | 
  233 |   test('shows validation error for invalid income', async ({ page }) => {
  234 |     await page.getByLabel('Applicant Name').fill('E2E Test User');
  235 |     await page.getByLabel('Annual Income (USD)').fill('-100');
  236 |     await page.getByLabel('Requested Loan Amount (USD)').fill('20000');
  237 |     await page.getByLabel('Debt Utilization Ratio').fill('0.25');
  238 |     await page.getByRole('button', { name: /create application/i }).click();
  239 |     // Either form validation or API error should be shown
  240 |     const errorText = page.getByText(/income must be positive|valid income/i);
  241 |     await expect(errorText).toBeVisible();
  242 |   });
  243 | 
  244 |   test('successful submission navigates to document upload', async ({ page }) => {
  245 |     await page.getByLabel('Applicant Name').fill('E2E Test User');
  246 |     await page.getByLabel('Annual Income (USD)').fill('90000');
  247 |     await page.getByLabel('Requested Loan Amount (USD)').fill('20000');
  248 |     await page.getByLabel('Debt Utilization Ratio').fill('0.20');
  249 | 
  250 |     await page.getByRole('button', { name: /create application/i }).click();
  251 | 
  252 |     // After success the app navigates to the upload step
  253 |     await expect(page).toHaveURL(
  254 |       new RegExp(`/applications/${GOLDEN_APPLICATION_ID}/upload`),
  255 |       { timeout: 10_000 }
  256 |     );
  257 |   });
  258 | });
  259 | 
  260 | test.describe('Decision View', () => {
  261 |   test.beforeEach(async ({ page }) => {
  262 |     await installApiMocks(page);
  263 |     await injectAuthToken(page);
  264 |     // Navigate directly to the decision page for the golden application
  265 |     await page.goto(`/applications/${GOLDEN_APPLICATION_ID}/decision`);
  266 |   });
  267 | 
  268 |   test('renders decision page without crashing', async ({ page }) => {
  269 |     await expect(page.locator('body')).not.toBeEmpty();
  270 |   });
  271 | 
  272 |   test('displays APPROVE outcome for PRIME golden applicant', async ({ page }) => {
  273 |     // The decision view should display the outcome text
  274 |     const approveText = page.getByText(/approve/i).first();
  275 |     await expect(approveText).toBeVisible({ timeout: 10_000 });
  276 |   });
  277 | 
  278 |   test('displays PRIME risk profile', async ({ page }) => {
  279 |     const primeText = page.getByText(/prime/i).first();
  280 |     await expect(primeText).toBeVisible({ timeout: 10_000 });
  281 |   });
  282 | });
  283 | 
  284 | test.describe('Full Application Flow (E2E)', () => {
  285 |   /**
  286 |    * Golden path: new application → upload docs (simulated) → submit → decision.
  287 |    *
  288 |    * The API responses are fully mocked so no backend or AWS is needed.
  289 |    */
  290 |   test('create → navigate to upload → check decision page', async ({ page }) => {
  291 |     await installApiMocks(page);
  292 |     await injectAuthToken(page);
  293 | 
  294 |     // Step 1: Start at the new-application form
  295 |     await page.goto('/applications/new');
  296 |     await expect(page.getByLabel('Applicant Name')).toBeVisible();
  297 | 
  298 |     // Step 2: Fill and submit the form
  299 |     await page.getByLabel('Applicant Name').fill('E2E Golden Prime User');
  300 |     await page.getByLabel('Annual Income (USD)').fill('90000');
  301 |     await page.getByLabel('Requested Loan Amount (USD)').fill('20000');
  302 |     await page.getByLabel('Debt Utilization Ratio').fill('0.20');
  303 |     await page.getByRole('button', { name: /create application/i }).click();
  304 | 
  305 |     // Step 3: Should navigate to upload page
  306 |     await expect(page).toHaveURL(
  307 |       new RegExp(`/applications/${GOLDEN_APPLICATION_ID}/upload`),
  308 |       { timeout: 10_000 }
  309 |     );
  310 | 
  311 |     // Step 4: Navigate directly to decision (skipping real file upload)
  312 |     await page.goto(`/applications/${GOLDEN_APPLICATION_ID}/decision`);
  313 | 
  314 |     // Step 5: Decision page should display APPROVE outcome
  315 |     const outcome = page.getByText(/approve/i).first();
```