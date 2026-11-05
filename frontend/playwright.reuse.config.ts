import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60000,
  expect: { timeout: 12000 },
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3100", viewport: { width: 1512, height: 1100 } },
});
