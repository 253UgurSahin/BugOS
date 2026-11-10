// Playwright for the BugOS website (website/). No accounts, so no sign-in setup.
// Start the site first, from the repo root:  python3 -m http.server 8080 --directory website
// Then, from e2e/:  FORGE_BASE_URL=http://localhost:8080 npx playwright test
import { defineConfig } from '@playwright/test';

export default defineConfig({
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.FORGE_BASE_URL || 'http://localhost:8080',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', testMatch: /\.spec\.ts$/ }],
});
