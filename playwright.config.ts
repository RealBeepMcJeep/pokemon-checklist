import { defineConfig, devices } from "@playwright/test";

// PW_PORT lets several checkouts (worktrees) run the suite at the same time.
const port = Number(process.env.PW_PORT ?? 4173);

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    ...devices["Desktop Chrome"],
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  },
  projects: [
    { name: "vite-dev", use: { baseURL: `http://127.0.0.1:${port}` } },
    { name: "standalone-file" },
  ],
});
