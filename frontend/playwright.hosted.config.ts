import { defineConfig } from "@playwright/test";
// Signed-in teams: workspaces, roles and isolation through the browser. Run after the main suite
// (Next.js allows one development server per folder).
export default defineConfig({
  testDir: "./e2e-hosted",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 12000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-hosted" }]],
  use: { baseURL: "http://127.0.0.1:3101", viewport: { width: 1440, height: 1000 }, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: { command: "../scripts/hosted-e2e-server.sh", url: "http://127.0.0.1:3101", reuseExistingServer: false, timeout: 180000 },
});
