import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const cors = { "access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type" };

test("research follows the brief, shows progress, partial failures and evidence", async ({ page }) => {
  let checks = 0;
  const progress = { phase: "searching", planned: 3, completed: 1, failed: 1, active_queries: ["hospital fire inspection"] };
  await page.route("**/api/intelligence/universal-research-jobs**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({ brief: "Find maintenance signals in English hospitals", max_searches: 3 });
      return route.fulfill({ headers: cors, json: { job_id: "test-1", status: "queued", progress, result: null, error: null } });
    }
    checks++;
    if (checks === 1) return route.fulfill({ headers: cors, json: { job_id: "test-1", status: "running", progress, result: null, error: null } });
    return route.fulfill({ headers: cors, json: { job_id: "test-1", status: "completed", progress, error: null, result: {
      brief: "Find maintenance signals in English hospitals", model: "gpt-6.1-terra",
      searches: [{ query: "hospital maintenance", status: "completed", detail: "", web_queries: ["hospital fire inspection"], web_sources: ["https://example.org/search-source"], stage: "initial" }, { query: "trust estates", status: "failed", detail: "Search failed", web_queries: [], web_sources: ["https://example.org/failed-output-source"], stage: "follow_up" }, { query: "fallback search", status: "completed", detail: "", web_queries: [], stage: "planned_fallback" }],
      observations: [
        { id: "1", source_title: "Hospital report", source_url: "https://example.org/report", published_date: "2026-01-01", fact: "A report describes an inspection.", origin: "evidence_inbox", organisation_name: "Example Trust", site: "East Campus", retrieved_at: "2026-04-01T10:00:00Z" },
        { id: "2", source_title: "Trust update", source_url: "https://example.org/update", published_date: "2026-02-01", fact: "The trust describes planned improvements." },
        { id: "3", source_title: "Trust response", source_url: "https://example.org/response", published_date: "2026-03-01", fact: "The trust reports corrective action." },
        { id: "4", source_title: "Planning Data", source_url: "https://www.planning.data.gov.uk/entity/1234", published_date: "2025-01-01", fact: "A public planning record exists.", origin: "rightclick_x", retrieved_at: "2026-04-01T10:00:00Z" },
      ],
      opportunities: [{ organisation: "Example Trust", location: "England", headline: "Review service coordination", thesis: "The signals may warrant a conversation; work may already be complete.", potential_solution: "Explore coordinated maintenance visits.", supporting_observation_ids: ["1", "2", "4"], counter_observation_ids: ["3"], unknowns: ["Current contract scope"], contact_name: "", contact_role: "Estates lead", contact_observation_ids: [], engagement: "Ask how work is coordinated.", verification_action: "Confirm the present arrangements." }],
      source_discovery: { status: "completed", message: "Planning source returned contextual records.", capabilities: [{ id: "planning.search", title: "Search planning records", provider: "Planning Data England", source: "https://www.planning.data.gov.uk" }], query: { identifier: "10008315764", dataset: "conservation-area", records: [{ entity_id: "1234", title: "Example conservation area", source_url: "https://www.planning.data.gov.uk/entity/1234", description: "", date: "2025-01-01" }], receipt: "receipt-123" } },
      limitations: ["The search is not exhaustive."],
    } } });
  });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  await research.getByLabel("Research brief").fill("Find maintenance signals in English hospitals");
  await research.getByLabel("Research breadth").selectOption("3");
  await research.getByRole("button", { name: "Research opportunities" }).click();
  await expect(research.getByRole("status")).toContainText("1 completed, 1 failed of 3 planned research passes");
  await expect(research.getByText("Review service coordination")).toBeVisible();
  const card = research.getByRole("article");
  await expect(card.getByText("A report describes an inspection.")).toBeVisible();
  await expect(card.locator("p").filter({ hasText: "Imported · unverified" })).toContainText("Site: East Campus");
  await expect(card.locator("p").filter({ hasText: "Imported · unverified" })).toContainText("Retrieved: 2026-04-01T10:00:00Z");
  await expect(card.locator("p").filter({ hasText: "Public API · unverified" })).toContainText("Confirm the identifier, location and source");
  await research.getByText("Public source discovery", { exact: false }).click();
  await expect(research.getByText("Planning source returned contextual records.")).toBeVisible();
  await expect(research.getByRole("link", { name: "View public record" })).toHaveAttribute("href", "https://www.planning.data.gov.uk/entity/1234");
  await expect(card.getByText("The trust reports corrective action.")).toBeVisible();
  await expect(card.getByText("Explore coordinated maintenance visits.")).toBeVisible();
  await expect(card.getByText(/not a confirmed requirement/)).toBeVisible();
  await expect(research.getByText("Current contract scope")).toBeVisible();
  await expect(research.getByText("Estates lead")).toBeVisible();
  await expect(card.getByRole("link", { name: /View source Hospital report/ })).toHaveAttribute("href", "https://example.org/report");
  await research.locator("summary").filter({ hasText: "Research passes and coverage" }).click();
  await expect(research.getByText("Initial pass · Completed:", { exact: false })).toBeVisible();
  await expect(research.getByText("Follow-up pass · Failed:", { exact: false })).toBeVisible();
  await expect(research.getByText("Planned fallback pass · Completed:", { exact: false })).toBeVisible();
  await expect(research.getByText("Web queries reported by the search tool:")).toBeVisible();
  await research.locator("summary").filter({ hasText: "URLs returned by search" }).nth(1).click();
  await expect(research.getByText(/Their contents and any claims have not been independently verified/).nth(1)).toBeVisible();
  await expect(research.getByRole("link", { name: "https://example.org/failed-output-source" })).toHaveAttribute("href", "https://example.org/failed-output-source");
  await expect(research.getByText("The search is not exhaustive.")).toBeVisible();
  await expect(research.getByText(/not been saved to the pipeline/)).toBeVisible();
  const downloading = page.waitForEvent("download");
  await research.getByRole("button", { name: "Download research JSON" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("misi-public-research.json");
  const downloadedPath = await download.path();
  expect(downloadedPath).not.toBeNull();
  const saved = JSON.parse(await readFile(downloadedPath!, "utf-8"));
  expect(saved.brief).toBe("Find maintenance signals in English hospitals");
  expect(saved.observations).toHaveLength(4);
  expect(saved.searches[1].status).toBe("failed");
  expect(saved.limitations).toContain("The search is not exhaustive.");
});

test("a research angle starts an editable brief without launching research", async ({ page }) => {
  let launched = false;
  await page.route("**/api/intelligence/universal-research-jobs", async (route) => { launched = true; await route.abort(); });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  await research.locator("summary").filter({ hasText: "Choose a research angle" }).click();
  await research.getByRole("button", { name: /Service friction/ }).click();
  await expect(research.getByLabel("Research brief")).toHaveValue(/do not attribute fault to a supplier/i);
  await research.getByLabel("Research brief").fill("Investigate manufacturers in Glasgow for possible alarm maintenance needs.");
  await expect(research.getByLabel("Research brief")).toHaveValue(/manufacturers in Glasgow/);
  expect(launched).toBe(false);
});

test("inbox inclusion is an explicit opt-in with a public-information warning", async ({ page }) => {
  let request: unknown;
  await page.route("**/api/intelligence/universal-research-jobs", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    request = route.request().postDataJSON();
    await route.fulfill({ status: 503, headers: cors, json: { detail: "Test stopped after request" } });
  });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  const inbox = research.getByLabel("Include matching evidence from your inbox");
  await expect(inbox).not.toBeChecked();
  await expect(research.locator("#public-research-inbox-note")).toContainText("sent to the configured AI provider");
  await expect(research.getByText(/only public information/)).toBeVisible();
  await inbox.check();
  await research.getByRole("button", { name: "Research opportunities" }).click();
  await expect.poll(() => request).toMatchObject({ include_inbox: true });
});

test("England planning context is an explicit opt-in", async ({ page }) => {
  let request: unknown;
  await page.route("**/api/intelligence/universal-research-jobs", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    request = route.request().postDataJSON();
    await route.fulfill({ status: 503, headers: cors, json: { detail: "Test stopped after request" } });
  });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  const discovery = research.getByLabel("Include England planning context");
  await expect(discovery).not.toBeChecked();
  await expect(research.locator("#public-research-rightclick-note")).toContainText("Its description and any returned records will be sent to the configured AI provider");
  await discovery.check();
  await research.getByLabel("UPRN or postcode, optional").fill("10008315764");
  await research.getByLabel("Planning dataset in England").selectOption("conservation-area");
  await research.getByRole("button", { name: "Research opportunities" }).click();
  await expect.poll(() => request).toMatchObject({ include_rightclick: true, rightclick_identifier: "10008315764", rightclick_dataset: "conservation-area" });
});

test("research reports empty results without presenting them as complete coverage", async ({ page }) => {
  const progress = { phase: "completed", planned: 1, completed: 1, failed: 0, active_queries: [] };
  await page.route("**/api/intelligence/universal-research-jobs**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const job = route.request().method() === "POST" ? { job_id: "test-2", status: "queued", progress, result: null, error: null } : {
      job_id: "test-2", status: "completed", progress, error: null,
      result: { brief: "Find maintenance signals in Wales", model: "gpt-6.1-terra", searches: [{ query: "Wales", status: "completed", detail: "", web_queries: [] }], observations: [], opportunities: [], limitations: ["Coverage is partial."] },
    };
    return route.fulfill({ headers: cors, json: job });
  });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  await research.getByLabel("Research brief").fill("Find maintenance signals in Wales");
  await research.getByRole("button", { name: "Research opportunities" }).click();
  await expect(research.getByText("No sufficiently supported opportunities found")).toBeVisible();
  await expect(research.getByText(/may not cover every source/)).toBeVisible();
});

test("research brief is usable at mobile width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  await expect(research.getByLabel("Research brief")).toBeVisible();
  await expect(research.getByLabel("Research breadth")).toBeVisible();
  await expect(research.getByRole("button", { name: "Research opportunities" })).toBeVisible();
  const box = await research.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(391);
});

test("food register context is sent only with explicit postcode opt-in", async ({ page }) => {
  let request: Record<string, unknown> = {};
  await page.route("**/api/intelligence/universal-research-jobs", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    request = route.request().postDataJSON();
    await route.fulfill({ status: 503, headers: cors, json: { detail: "Test stopped after request" } });
  });
  await page.goto("/?view=discover");
  const research = page.getByRole("region", { name: "Public opportunity research" });
  const register = research.getByLabel("Check the UK food establishments register");
  await expect(register).not.toBeChecked();
  await register.check();
  await research.getByLabel("Full UK postcode").fill("SW1A 1AA");
  await research.getByRole("button", { name: "Research opportunities" }).click();
  await expect.poll(() => request).toMatchObject({ include_estate_lookup: true, estate_postcode: "SW1A 1AA" });
});
