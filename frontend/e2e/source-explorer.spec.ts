import { expect, test } from "@playwright/test";

const cors = { "access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type" };

test("source explorer discovers and explains an approved public capability", async ({ page }) => {
  const requested: string[] = [];
  await page.route("**/api/rightclick/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const url = new URL(route.request().url());
    requested.push(url.pathname);
    if (url.pathname.endsWith("/candidates")) {
      expect(url.searchParams.get("topic")).toBe("fire safety");
      return route.fulfill({ headers: cors, json: { topic: "fire safety", candidates: [{ title: "Example public API", description: "Possible source to review.", directory: "Example registry", kind: "openapi" }], directories: [{ id: "Example registry", reachable: true }], message: "Candidates require review." } });
    }
    if (url.pathname.endsWith("/planning-query")) {
      expect(route.request().postDataJSON()).toEqual({ identifier: "10008315764", dataset: "conservation-area", limit: 10 });
      return route.fulfill({ headers: cors, json: { source: "https://www.planning.data.gov.uk", source_contract: "https://www.planning.data.gov.uk/openapi.json", dataset: "conservation-area", query: "10008315764", entities: [{ entity: 1234, dataset: "conservation-area", name: "Example conservation area", "start-date": "2020-01-01" }, { entity: "9999", dataset: "brownfield-land", name: "Wrong dataset" }, { entity: "invalid/path", dataset: "conservation-area", name: "Unlinked record" }], receipt: { run_id: "run-123" }, verification: "unverified", limitations: ["Coverage may be incomplete."] } });
    }
    if (url.pathname.endsWith("/status")) return route.fulfill({ headers: cors, json: { available: true, configured: true, version: "0.1.0", capabilities: 1, message: "Approved public sources available." } });
    if (url.pathname.endsWith("/capabilities/explain")) return route.fulfill({ headers: cors, json: { id: "planning.search", title: "Search planning records", provider: "Planning Data England", risk: "read", method: "GET", origin: "https://www.planning.data.gov.uk", inputs: [{ name: "q", type: "postcode or UPRN", required: false }], limitations: ["Coverage varies; an empty result does not establish no activity."], message: "Public source contract; review before use." } });
    return route.fulfill({ headers: cors, json: { items: [{ id: "planning.search", title: "Search planning records", provider: "Planning Data England", source: "https://www.planning.data.gov.uk" }], message: "1 approved capability found." } });
  });
  await page.goto("/?view=discover");
  const explorer = page.getByRole("region", { name: "Public source explorer" });
  expect(requested).toEqual([]);
  await explorer.locator("summary").click();
  await expect(explorer.getByText("Discovery available")).toBeVisible();
  await explorer.getByRole("button", { name: "Find source candidates" }).click();
  await expect(explorer.getByText("Example public API")).toBeVisible();
  await expect(explorer.getByText(/Unreviewed · Example registry/)).toBeVisible();
  await expect(explorer.getByText(/not approved for MiSi research/)).toBeVisible();
  await explorer.getByRole("button", { name: "Show approved capability" }).click();
  await expect(explorer.getByText("1 approved capability found.")).toBeVisible();
  await explorer.getByRole("button", { name: /Search planning records/ }).click();
  const detail = explorer.getByRole("article", { name: "Capability details" });
  await expect(detail.getByText("postcode or UPRN", { exact: false })).toBeVisible();
  await expect(detail.getByText(/Coverage varies/)).toBeVisible();
  await expect(detail.getByRole("link", { name: "Visit source" })).toHaveAttribute("href", "https://www.planning.data.gov.uk/");
  await explorer.getByLabel("UPRN or postcode", { exact: true }).fill("10008315764");
  await explorer.getByLabel("Public dataset").selectOption("conservation-area");
  await explorer.getByRole("button", { name: "Check public planning data" }).click();
  await expect(explorer.getByText("Example conservation area")).toBeVisible();
  await expect(explorer.getByText("Wrong dataset")).toHaveCount(0);
  await expect(explorer.getByText("Unlinked record")).toBeVisible();
  await expect(explorer.getByRole("link", { name: "View official record" })).toHaveCount(1);
  await expect(explorer.getByText(/omitted because their dataset did not match/)).toBeVisible();
  await expect(explorer.getByRole("link", { name: "View official record" })).toHaveAttribute("href", "https://www.planning.data.gov.uk/entity/1234");
  await expect(explorer.getByText(/no results does not mean no activity/i)).toBeVisible();
  await explorer.getByText("View execution receipt").click();
  await expect(explorer.getByText(/run-123/)).toBeVisible();
  expect(requested).toEqual(["/api/rightclick/status", "/api/rightclick/candidates", "/api/rightclick/capabilities", "/api/rightclick/capabilities/explain", "/api/rightclick/planning-query"]);
});

test("unconfigured source explorer stays usable and makes no capability request", async ({ page }) => {
  const requested: string[] = [];
  await page.route("**/api/rightclick/**", async (route) => {
    const url = new URL(route.request().url()); requested.push(url.pathname);
    await route.fulfill({ headers: cors, json: { available: false, configured: false, version: null, capabilities: null, message: "Connect RightClick-X in backend settings." } });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=discover");
  const explorer = page.getByRole("region", { name: "Public source explorer" });
  await explorer.locator("summary").click();
  await expect(explorer.getByText("Not configured")).toBeVisible();
  await expect(explorer.getByText("Connect public source discovery in backend settings.")).toBeVisible();
  await expect(explorer.getByRole("button", { name: "Show approved capability" })).toHaveCount(0);
  expect(requested).toEqual(["/api/rightclick/status"]);
  const box = await explorer.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(391);
});
