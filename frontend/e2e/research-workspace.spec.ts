import { expect, test } from "@playwright/test";

const cors = { "access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-methods": "GET,POST,PATCH,OPTIONS", "access-control-allow-headers": "content-type" };

test("a salesperson can review saved evidence, update a lead and research a public contact", async ({ page }) => {
  const lead = {
    id: 17, run_id: 4, organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", status: "new", notes: "", updated_at: "2026-10-28", brief: "Find maintenance signals", model: "gpt-6.1-terra", feedback: [],
    opportunity: { organisation: "Example Trust", location: "Yorkshire", headline: "Review maintenance arrangements", thesis: "Separate estate signals suggest a conversation may be timely.", potential_solution: "Explore a coordinated maintenance review.", supporting_observation_ids: ["one"], counter_observation_ids: ["two"], unknowns: ["Current provider"], contact_name: "", contact_role: "Estates lead", contact_observation_ids: [], engagement: "Ask how they coordinate maintenance.", verification_action: "Confirm current arrangements." },
    source_discovery: { status: "searched", message: "Public planning context was returned.", capabilities: [{ id: "planning.search", title: "Planning Data England", provider: "Approved public source", source: "https://www.planning.data.gov.uk" }], query: { identifier: "10008315764", dataset: "conservation-area", records: [{ entity_id: "1234", title: "Conservation area context", source_url: "https://www.planning.data.gov.uk/entity/1234", description: "Check geographic relevance.", date: "2020-01-01" }, { entity_id: "99", title: "Untrusted source record", source_url: "https://example.org/not-official", description: "", date: "" }], receipt: "receipt-123" } },
    related_observations: [{ id: 82, organisation_name: "Example Trust", site: "Unspecified", observed_statement: "A historical contract was published.", source_title: "Award notice", source_url: "https://example.org/award", published_at: "2025-03-01", retrieved_at: "2026-10-28" }], related_observations_note: "Confirm identity and site.",
    actions: [] as Array<{ id: number; lead_id: number; text: string; due_date: string | null; status: string }>,
    observations: [{ id: "one", source_title: "Estate report", source_url: "https://example.org/estate", published_date: "2026-01-01", fact: "Estate upgrades were planned.", origin: "evidence_inbox", organisation_name: "Example Trust", site: "East Campus", retrieved_at: "2026-04-01T10:00:00Z" }, { id: "two", source_title: "Progress report", source_url: "https://example.org/progress", published_date: "2026-02-01", fact: "Some works were completed." }],
  };
  const updates: unknown[] = [];
  let finishStageUpdate: (() => void) | undefined;
  let contactCalls = 0;
  let actionRequest: unknown;
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (route.request().url().endsWith("/leads/17/actions") && route.request().method() === "POST") {
      actionRequest = route.request().postDataJSON();
      const action = { id: 51, lead_id: 17, ...route.request().postDataJSON(), status: "open" };
      lead.actions.unshift(action);
      return route.fulfill({ headers: cors, json: action });
    }
    if (route.request().url().endsWith("/actions/51") && route.request().method() === "PATCH") {
      const action = Object.assign(lead.actions[0], route.request().postDataJSON());
      return route.fulfill({ headers: cors, json: action });
    }
    if (route.request().url().includes("/contact-research")) {
      contactCalls += 1;
      const snapshot = { result: { organisation: "Example Trust", contacts: [{ name: "", role: "", kind: "email", value: "estates@example.org", source_url: "https://example.org/contact", source_title: "Published contact", source_date: "", evidence_quote: "Contact estates@example.org" }], limitations: ["Confirm before use."] }, researched_at: "2026-10-28T12:00:00Z", saved: true, save_error: null };
      Object.assign(lead, { contact_research: snapshot });
      return route.fulfill({ headers: cors, json: snapshot });
    }
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON(); updates.push(body); Object.assign(lead, body);
      if (body.status) await new Promise<void>((resolve) => { finishStageUpdate = resolve; });
      return route.fulfill({ headers: cors, json: lead });
    }
    if (route.request().url().includes("/runs?")) return route.fulfill({ headers: cors, json: { items: [{ id: 4, brief: "Earlier research with no leads", model: "gpt-6.1-terra", completed_at: "2026-10-28", result: { searches: [], observations: [], opportunities: [], limitations: ["Partial coverage"] } }], total: 1 } });
    if (route.request().url().includes("/leads?")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await workspace.getByText("Recent research runs", { exact: false }).click();
  await expect(workspace.getByText("Earlier research with no leads")).toBeVisible();
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  await expect(workspace.getByText("Separate estate signals suggest a conversation may be timely.")).toBeVisible();
  await workspace.getByLabel("Action", { exact: true }).fill("Review the site with the estates lead");
  await workspace.getByLabel("Due date, optional").fill("2026-11-01");
  await workspace.getByRole("button", { name: "Add next move" }).click();
  await expect.poll(() => actionRequest).toEqual({ text: "Review the site with the estates lead", due_date: "2026-11-01" });
  await expect(workspace.getByText("Next move saved. Find it on Today.")).toBeVisible();
  const nextMoves = workspace.getByRole("region", { name: "Next moves" });
  await expect(nextMoves.getByText("Review the site with the estates lead")).toBeVisible();
  await nextMoves.getByRole("button", { name: "Defer" }).click();
  await expect(nextMoves.getByText(/Deferred/)).toBeVisible();
  await nextMoves.getByRole("button", { name: "Reopen" }).click();
  await nextMoves.getByRole("button", { name: "Edit" }).click();
  await nextMoves.getByLabel("Edit next move").fill("Review the site and confirm the right contact");
  await nextMoves.getByRole("button", { name: "Save move" }).click();
  await expect(nextMoves.getByText("Review the site and confirm the right contact")).toBeVisible();
  await nextMoves.getByRole("button", { name: "Mark done" }).click();
  await expect(nextMoves.getByText(/Completed/)).toBeVisible();
  await workspace.getByText("Prepare for a conversation").click();
  await expect(workspace.getByText("Research hypothesis — verify before use")).toBeVisible();
  await expect(workspace.getByText(/Some works were completed/, { exact: false }).first()).toBeVisible();
  await workspace.getByText("Prepare for a conversation").click();
  await workspace.getByText("Evidence and public sources").click();
  await workspace.getByText("Public source discovery", { exact: false }).click();
  await expect(workspace.getByText("Public planning context was returned.")).toBeVisible();
  await expect(workspace.getByText("Conservation area context")).toBeVisible();
  await expect(workspace.getByText(/Unverified contextual records/)).toBeVisible();
  await expect(workspace.getByText("Execution receipt: receipt-123")).toBeVisible();
  await expect(workspace.getByRole("link", { name: "View public record" })).toHaveAttribute("href", "https://www.planning.data.gov.uk/entity/1234");
  await expect(workspace.getByText("Some works were completed.")).toBeVisible();
  await expect(workspace.locator("p").filter({ hasText: "Imported · unverified" })).toContainText("Site: East Campus");
  await expect(workspace.locator("p").filter({ hasText: "Imported · unverified" })).toContainText("Retrieved: 2026-04-01T10:00:00Z");
  await expect(workspace.getByLabel("Evidence overview")).toContainText("Linked observations: 1");
  await expect(workspace.getByLabel("Evidence overview")).toContainText("Alternative context: 1");
  await expect(workspace.getByText("Explore a coordinated maintenance review.")).toBeVisible();
  await expect(workspace.getByText(/not a confirmed requirement or delivery capability/)).toBeVisible();
  await expect(workspace.getByRole("link", { name: "Read source" }).first()).toHaveAttribute("href", "https://example.org/estate");
  await expect(workspace.getByText("Current provider")).toBeVisible();
  await workspace.getByText("Related evidence from your inbox", { exact: false }).click();
  await expect(workspace.getByText("A historical contract was published.")).toBeVisible();
  await expect(workspace.getByRole("link", { name: "Award notice" })).toHaveAttribute("href", "https://example.org/award");
  await workspace.getByLabel("Sales stage").selectOption("investigate");
  await expect.poll(() => updates).toContainEqual({ status: "investigate" });
  await workspace.getByLabel("Your notes").fill("Check contract scope");
  expect(finishStageUpdate).toBeDefined();
  finishStageUpdate!();
  await expect(workspace.getByLabel("Your notes")).toHaveValue("Check contract scope");
  await workspace.getByRole("button", { name: "Save notes" }).click();
  await expect.poll(() => updates).toContainEqual({ notes: "Check contract scope" });
  await workspace.getByRole("button", { name: "Useful", exact: true }).click();
  await expect.poll(() => updates).toContainEqual({ feedback: "useful" });
  await workspace.getByRole("button", { name: "Find public contact details" }).click();
  await expect(workspace.getByText("estates@example.org", { exact: true })).toBeVisible();
  await expect(workspace.getByText(/independent checking/)).toBeVisible();
  await expect(workspace.getByRole("link", { name: "Published contact" })).toHaveAttribute("href", "https://example.org/contact");
  await page.reload();
  await workspace.getByRole("button", { name: /Example Trust/ }).click();
  await expect(workspace.getByText("estates@example.org", { exact: true })).toBeVisible();
  await workspace.getByText("Evidence and public sources").click();
  await workspace.getByText("Public source discovery", { exact: false }).click();
  await expect(workspace.getByText("Conservation area context")).toBeVisible();
  expect(contactCalls).toBe(1);
});

test("the research workspace remains usable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/research-dossiers/**", async (route) => route.fulfill({ headers: cors, json: { items: [], total: 0 } }));
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await expect(workspace.getByText("Your first lead starts with a question")).toBeVisible();
  const box = await workspace.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(391);
});

test("older saved leads without source discovery still open", async ({ page }) => {
  const lead = { id: 42, run_id: 1, organisation: "Historic Trust", location: "England", headline: "Review site", status: "new", notes: "", updated_at: "2026-01-01", brief: "Historic research", model: "gpt-6.1-terra", feedback: [], observations: [], opportunity: { organisation: "Historic Trust", location: "England", headline: "Review site", thesis: "Historical snapshot remains available.", supporting_observation_ids: [], counter_observation_ids: [], unknowns: [], contact_name: "", contact_role: "Estates lead", contact_observation_ids: [], engagement: "Ask a question.", verification_action: "Verify the site." } };
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().url().includes("/leads?")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    if (route.request().url().includes("/runs?")) return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
    return route.fulfill({ headers: cors, json: lead });
  });
  await page.goto("/?view=discover");
  const workspace = page.getByRole("region", { name: "Saved research workspace" });
  await workspace.getByRole("button", { name: /Historic Trust/ }).click();
  await expect(workspace.getByText("Historical snapshot remains available.")).toBeVisible();
  await expect(workspace.getByText(/Public source discovery/)).toHaveCount(0);
});

test("historical public-sector feed shows bounded coverage and continues the same window", async ({ page }) => {
  const bodies: unknown[] = [];
  await page.route("**/api/public-sources/find-a-tender/refresh", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    bodies.push(route.request().postDataJSON());
    return route.fulfill({ headers: cors, json: { imported: 2, duplicates: 1, scanned: 50, matched: 3, pages: 2, updated_from: "2026-10-21T00:00:00Z", updated_to: "2026-10-28T00:00:00Z", next_cursor: bodies.length === 1 ? "abc123" : null, warnings: ["Historical awards are context, not active demand."] } });
  });
  await page.goto("/?view=discover");
  await page.getByText("Review your evidence inbox", { exact: true }).click();
  const inbox = page.getByRole("region", { name: "Evidence inbox" });
  await inbox.getByRole("button", { name: "Refresh historical public-sector context" }).click();
  await expect(inbox.getByText(/2 observations added/)).toBeVisible();
  await expect(inbox.getByText("Historical awards are context, not active demand.")).toBeVisible();
  await inbox.getByRole("button", { name: "Check next pages" }).click();
  await expect.poll(() => bodies).toEqual([{}, { updated_from: "2026-10-21T00:00:00Z", updated_to: "2026-10-28T00:00:00Z", cursor: "abc123" }]);
});


test("returning from Today focuses the requested research even when the list is empty", async ({ page }) => {
  const lead = { id: 66, run_id: 1, organisation: "Return Trust", location: "Wales", headline: "Review arrangements", status: "new", notes: "", updated_at: "2026-01-01", brief: "Past research", model: "configured model", feedback: [], observations: [], actions: [], opportunity: { organisation: "Return Trust", location: "Wales", headline: "Review arrangements", thesis: "A possible conversation to verify.", supporting_observation_ids: [], counter_observation_ids: [], unknowns: [], contact_name: "", contact_role: "", contact_observation_ids: [], engagement: "Ask about current arrangements.", verification_action: "Verify the organisation." } };
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().url().includes("/leads/66")) return route.fulfill({ headers: cors, json: lead });
    return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
  });
  await page.addInitScript(() => sessionStorage.setItem("misi-open-lead", "66"));
  await page.goto("/?view=discover");
  const detail = page.getByRole("region", { name: "Research brief for Return Trust" });
  await expect(detail).toBeVisible();
  await expect(detail).toBeFocused();
});
