import { expect, test } from "@playwright/test";

const timing = {
  phase: "engage_now", light: "green", label: "Engage now", window: { start: "2026-11-04", end: "2027-06-01" },
  convergence: { start: "2026-11-04", end: "2027-03-01", kinds: ["leadership_change", "site_opening"], labels: ["New decision maker", "New site opening"] },
  blocked_until: null, reasons: ["2 independent clues converge from Nov 2026 to Mar 2027: New decision maker, New site opening."], as_of: "2026-11-04",
  method: "Inferred from indirect, dated clues using industry rules of thumb. A phase, not a probability.",
  clues: [
    { kind: "site_opening", label: "New site opening", detail: "Daventry DC opens autumn 2027", basis: "stated", strength: "strong", observed: "2027-09-01", precision: "day", source_url: "https://news.example.co.uk/acme", system_family: "", polarity: 1, start: "2026-09-01", end: "2027-06-01", rule: "fire and security for a new site is usually procured three to twelve months before it opens", status: "active" },
    { kind: "leadership_change", label: "New decision maker", detail: "New Head of Property", basis: "stated", strength: "strong", observed: "2026-10-15", precision: "day", source_url: "https://news.example.co.uk/acme", system_family: "", polarity: 1, start: "2026-11-15", end: "2027-07-15", rule: "new leaders review suppliers", status: "upcoming" },
  ],
};
const prospect = {
  id: 7, name: "Acme Logistics Ltd", status: "new", opportunity_id: null, created_at: "2026-11-04", updated_at: "2026-11-04",
  website: "https://www.acme-logistics.co.uk", sector: "Logistics", location: "Daventry", company_number: "", size: "",
  headline: "New 400,000 sq ft distribution centre opening next autumn.", summary: "Acme is expanding.",
  signals: [{ type: "new_site", title: "New distribution centre", detail: "Construction under way.", date: "2026-09", basis: "stated", direction: "supports", source_url: "https://news.example.co.uk/acme" }],
  incumbent: { name: "", detail: "", basis: "unknown", source_url: "" }, competitors: [],
  people: [{ name: "Jane Smith", role: "Head of Property", influence: "decision_maker", why: "Owns the new site programme.", source_url: "https://news.example.co.uk/acme", quote: "said Jane Smith, Head of Property" }],
  contact_routes: [{ kind: "email", value: "facilities@acme-logistics.co.uk", label: "Facilities team", source_url: "https://www.acme-logistics.co.uk/contact", quote: "facilities@acme-logistics.co.uk" }],
  approach: { angle: "Design-in fire and security for the new site.", opening_line: "Congratulations on Daventry.", offer: "A design review.", questions: ["Who owns fit-out?"] },
  services: ["fire_alarm", "cctv"], unknowns: [], timing, signal_groups: ["Growth"], signal_labels: { new_site: "New site, warehouse or office" },
};

test("a sales person can hunt, read the timing inference and add a prospect to the pipeline", async ({ page }) => {
  let polled = 0;
  let promoted = 0;
  let started = "";
  await page.route("**/api/prospects**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (url.pathname.endsWith("/prospects/searches") && method === "POST") { started = route.request().postDataJSON().query; return route.fulfill({ json: { id: 3, query: started, mode: "discover", status: "running", error: null, prospect_ids: [], sources_reviewed: 0, created_at: "", finished_at: null } }); }
    if (url.pathname.endsWith("/prospects/searches")) return route.fulfill({ json: { items: [] } });
    if (url.pathname.endsWith("/searches/3")) { polled += 1; return route.fulfill({ json: { id: 3, query: started, mode: "discover", status: "complete", error: null, prospect_ids: [7], sources_reviewed: 42, created_at: "", finished_at: "" } }); }
    if (url.pathname.endsWith("/7/promote")) { promoted += 1; return route.fulfill({ json: { opportunity_id: 11, created: true } }); }
    return route.fulfill({ json: { items: polled ? [{ ...prospect, status: promoted ? "pipeline" : "new" }] : [] } });
  });
  await page.goto("/?view=prospects");
  await expect(page.getByRole("heading", { name: "Prospects", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "PSTN switch-off exposure" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Researching" })).toBeVisible();
  expect(started).toContain("PSTN");
  const detail = page.getByRole("complementary", { name: "Selected prospect" });
  await expect(detail.getByRole("heading", { name: "Acme Logistics Ltd" })).toBeVisible({ timeout: 15000 });
  await expect(detail.getByText("Engage now").first()).toBeVisible();
  await detail.getByRole("tab", { name: /Timing/ }).click();
  await expect(detail.getByRole("region", { name: "Timing timeline" })).toBeVisible();
  await expect(detail.getByText(/independent clues converge/).first()).toBeVisible();
  await detail.getByRole("tab", { name: /People & contacts/ }).click();
  await expect(detail.getByText("Jane Smith", { exact: true })).toBeVisible();
  await expect(detail.getByRole("link", { name: "facilities@acme-logistics.co.uk" })).toHaveAttribute("href", "mailto:facilities@acme-logistics.co.uk");
  await detail.getByRole("button", { name: "Add to pipeline" }).click();
  await expect.poll(() => promoted).toBe(1);
  await expect(detail.getByRole("button", { name: "In your pipeline" })).toBeVisible();
});
