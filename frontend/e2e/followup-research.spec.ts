import { expect, test } from "@playwright/test";

const cors = { "access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type" };
const lead = {
  id: 17, run_id: 4, organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", status: "new", notes: "", updated_at: "2026-10-28", brief: "Find maintenance signals", model: "research model", feedback: [], actions: [],
  opportunity: { organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", thesis: "Estate signals may warrant a conversation.", supporting_observation_ids: ["one"], counter_observation_ids: ["two"], unknowns: ["Current provider"], contact_name: "", contact_role: "Estates lead", contact_observation_ids: [], engagement: "Ask how maintenance is coordinated.", verification_action: "Confirm current arrangements." },
  observations: [{ id: "one", source_title: "Estate report", source_url: "https://example.org/report", published_date: "2026-01-01", fact: "Estate upgrades were planned." }, { id: "two", source_title: "Progress report", source_url: "https://example.org/progress", published_date: "2026-02-01", fact: "Some works were completed." }],
};

test("a salesperson can ask a scoped follow-up and review a separately saved result", async ({ page }) => {
  let submitted: unknown;
  let pollCount = 0;
  const item = { id: 90, lead_id: 17, question: "Who currently oversees the maintenance programme?", job_id: "followup-job", status: "running", saved_run_id: null, created_at: "2026-10-28T12:00:00Z", progress: { phase: "searching", planned: 3, completed: 1, failed: 0, active_queries: [] }, error: null, save_error: null };
  let history: unknown[] = [];
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/leads/17/investigations")) {
      if (route.request().method() === "POST") { submitted = route.request().postDataJSON(); history = [item]; return route.fulfill({ headers: cors, json: item }); }
      return route.fulfill({ headers: cors, json: { items: history, total: history.length } });
    }
    if (url.pathname.endsWith("/investigations/90")) { pollCount += 1; const complete = { ...item, status: "completed", saved_run_id: 21, progress: { phase: "completed", planned: 3, completed: 3, failed: 0 } }; history = [complete]; return route.fulfill({ headers: cors, json: complete }); }
    if (url.pathname.endsWith("/runs/21")) return route.fulfill({ headers: cors, json: { id: 21, leads: [{ id: 22, organisation: "Example Trust", location: "Yorkshire", headline: "Check programme ownership", opportunity: { thesis: "A public document names a team; its present responsibility remains unverified.", verification_action: "Confirm the current team." } }], result: { observations: [{ id: "x", fact: "A public report names a team.", source_title: "Public report", source_url: "https://example.org/team", published_date: "2026-02-01" }], searches: [{}], limitations: ["The report may be out of date."] } } });
    if (url.pathname.endsWith("/runs")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    if (url.pathname.endsWith("/leads")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  await workspace.getByText("Ask a follow-up about Example Trust").click();
  await expect(workspace.getByText(/up to one cited web observation/)).toBeVisible();
  await workspace.getByLabel("Your follow-up question").fill(item.question);
  await workspace.getByLabel("Research breadth").last().selectOption("3");
  await workspace.getByRole("button", { name: "Research follow-up" }).click();
  await expect.poll(() => submitted).toEqual({ question: item.question, max_searches: 3 });
  await expect(workspace.getByText(/Researching · searching/)).toBeVisible();
  await expect(workspace.getByRole("status").filter({ hasText: "Saved" })).toBeVisible({ timeout: 10000 });
  expect(pollCount).toBeGreaterThan(0);
  await workspace.getByRole("button", { name: "View findings" }).click();
  await expect(workspace.getByText("Check programme ownership")).toBeVisible();
  await expect(workspace.getByText(/present responsibility remains unverified/)).toBeVisible();
  await workspace.getByText("Inspect gathered observations", { exact: false }).click();
  await expect(workspace.getByRole("link", { name: "Review source" })).toHaveAttribute("href", "https://example.org/team");
  await workspace.getByText("Coverage and limitations").click();
  await expect(workspace.getByText("The report may be out of date.")).toBeVisible();
  await page.reload();
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  await workspace.getByText("Ask a follow-up about Example Trust").click();
  await expect(workspace.getByText(item.question, { exact: true })).toBeVisible();
  await expect(workspace.getByRole("button", { name: "View findings" })).toBeVisible();
});

test("the evidence map distinguishes cited context, gaps and unverified identity", async ({ page }) => {
  await page.route("**/api/research-dossiers/**", async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (url.pathname.endsWith("/evidence-map")) return route.fulfill({ headers: cors, json: { lead_id: 17, nodes: [{ id: "organisation", type: "organisation", label: "Example Trust" }, { id: "stakeholder_role", type: "stakeholder_role", label: "Estates lead" }, { id: "observation:two", type: "observation", label: "Some works were completed.", source_title: "Progress report", published_date: "2026-02-01" }, { id: "source:two", type: "source", label: "Progress report", url: "https://example.org/progress" }], edges: [{ source: "observation:two", target: "hypothesis", relation: "counter_context" }, { source: "source:two", target: "observation:two", relation: "attributed_to" }], missing_references: [{ id: "missing", relation: "supports_hypothesis", reason: "missing" }], unknowns: ["Current provider"], limitations: ["The map is not a verified graph."] } });
    if (url.pathname.endsWith("/runs")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    if (url.pathname.endsWith("/leads")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  const map = workspace.getByText("Map the evidence connections").locator("xpath=..");
  await map.getByText("Map the evidence connections").click();
  await expect(map.getByText(/unverified dossier references/)).toBeVisible();
  await expect(map.getByText("Alternative context", { exact: true })).toBeVisible();
  await expect(map.getByText("Some works were completed.", { exact: true })).toBeVisible();
  await expect(map.getByRole("link", { name: "Review source" })).toHaveAttribute("href", "https://example.org/progress");
  await expect(map.getByText(/1 cited reference is missing/)).toBeVisible();
  await map.getByText("What this map can and cannot show").click();
  await expect(map.getByText("The map is not a verified graph.")).toBeVisible();
});

test("a late follow-up response stays with its original lead", async ({ page }) => {
  const second = { ...lead, id: 18, organisation: "Second Trust", opportunity: { ...lead.opportunity, organisation: "Second Trust" } };
  const question = "Who oversees the maintenance programme?";
  const item = { id: 91, lead_id: 17, question, job_id: "pending-job", status: "queued", saved_run_id: null, created_at: "2026-10-28T12:00:00Z", progress: null, error: null, save_error: null };
  let submitted = false;
  let finish: (() => void) | undefined;
  let saved = false;
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/leads/17/investigations") && route.request().method() === "POST") {
      submitted = true;
      await new Promise<void>((resolve) => { finish = resolve; });
      saved = true;
      return route.fulfill({ headers: cors, json: item });
    }
    if (path.endsWith("/leads/17/investigations")) return route.fulfill({ headers: cors, json: { items: saved ? [item] : [], total: saved ? 1 : 0 } });
    if (path.endsWith("/leads/18/investigations")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    if (path.endsWith("/leads/18")) return route.fulfill({ headers: cors, json: second });
    if (path.endsWith("/runs")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    if (path.endsWith("/leads")) return route.fulfill({ headers: cors, json: { items: [lead, second], total: 2 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  await workspace.getByText("Ask a follow-up about Example Trust").click();
  await workspace.getByLabel("Your follow-up question").fill(question);
  await workspace.getByRole("button", { name: "Research follow-up" }).click();
  await expect.poll(() => submitted).toBe(true);
  await workspace.getByRole("button", { name: /Second Trust/ }).click();
  await workspace.getByText("Ask a follow-up about Second Trust").click();
  finish!();
  await expect.poll(() => saved).toBe(true);
  await expect(workspace.getByLabel("Your follow-up question")).toHaveValue("");
  await expect(workspace.getByText(question, { exact: true })).toHaveCount(0);
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  await workspace.getByText("Ask a follow-up about Example Trust").click();
  await expect(workspace.getByText(question, { exact: true })).toBeVisible();
});
