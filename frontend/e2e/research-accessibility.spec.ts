import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const cors = { "access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-methods": "GET,OPTIONS", "access-control-allow-headers": "content-type" };

test("the selected research briefing has accessible evidence and action controls", async ({ page }) => {
  const lead = {
    id: 217, run_id: 4, organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", status: "new", notes: "", updated_at: "2026-10-28", brief: "Find maintenance signals", model: "research model", feedback: [], actions: [],
    opportunity: { organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", thesis: "Estate signals warrant a conversation; current arrangements remain unknown.", supporting_observation_ids: ["one"], counter_observation_ids: [], unknowns: ["Current provider"], contact_name: "", contact_role: "Estates lead", contact_observation_ids: [], engagement: "Ask how maintenance is coordinated.", verification_action: "Confirm current arrangements." },
    observations: [{ id: "one", source_title: "Estate report", source_url: "https://example.org/estate", published_date: "2026-01-01", fact: "Estate upgrades were planned." }],
  };
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (route.request().url().includes("/runs?")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    if (route.request().url().includes("/leads?")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  const briefing = page.getByRole("region", { name: "Research brief for Example Trust" });
  await expect(briefing.getByRole("heading", { name: "Review maintenance arrangements" })).toBeVisible();
  const scan = await new AxeBuilder({ page }).include('[aria-label="Research brief for Example Trust"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
});

test("the daily research briefing maintains accessible contrast and controls", async ({ page }) => {
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (route.request().url().includes("/leads?")) return route.fulfill({ headers: cors, json: { total: 1, items: [{ id: 1, organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", created_at: "2026-10-28T12:00:00Z", opportunity: { thesis: "Estate information suggests a question to verify.", verification_action: "Confirm current arrangements." } }] } });
    return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
  });
  await page.goto("/?view=today");
  await expect(page.getByRole("region", { name: "Research briefing" }).getByText("Review maintenance arrangements")).toBeVisible();
  const scan = await new AxeBuilder({ page }).include('[aria-label="Research briefing"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
});

test("opening a lead on mobile brings its briefing into view and focus", async ({ page }) => {
  const lead = { id: 217, run_id: 4, organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", status: "new", notes: "", updated_at: "2026-10-28", brief: "Find maintenance signals", model: "research model", feedback: [], actions: [], opportunity: { organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", thesis: "A question to verify.", supporting_observation_ids: [], counter_observation_ids: [], unknowns: [], contact_name: "", contact_role: "", contact_observation_ids: [], engagement: "Ask how maintenance is coordinated.", verification_action: "Confirm current arrangements." }, observations: [] };
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (route.request().url().includes("/runs?")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    if (route.request().url().includes("/leads?")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  await page.getByRole("region", { name: "Saved research workspace" }).getByRole("button", { name: /Example Trust/ }).click();
  await expect(page.getByRole("region", { name: "Research brief for Example Trust" })).toBeFocused();
});

test("discovery research and source controls are readable on the light workspace", async ({ page }) => {
  await page.goto("/?view=discover");
  await page.getByRole("region", { name: "Public source explorer" }).getByText("Find the public sources behind the signals", { exact: true }).click();
  const scan = await new AxeBuilder({ page })
    .include('[aria-label="Public opportunity research"]')
    .include('[aria-label="Public source explorer"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
});
