import { expect, test } from "@playwright/test";

const suggestion = {
  category: "contract_defence", category_label: "Contract defence", customer: "West London NHS Trust", title: "Security Systems Maintenance at Broadmoor Hospital", supplier: "Mitie Security Limited",
  timing: "2027-08-31", timing_basis: "published award contract period", end_estimated: false, latest_end: null, nation: "England", fit: "core",
  value: { published_total: 719994, estimated_annualised: 240382, framework_ceiling: null, type: "estimated_annualised", basis: "Published award value divided by the published term of 3.0 years.", scope_note: "" },
  priority: { tier: 1, reasons: ["Core fit"] }, counter_evidence: [], next_actions: ["Escalate to the account lead for retention planning."], extension: "",
  link: { confidence: "exact", records: 1, sources: ["Contracts Finder"] },
  brief: { customer: "West London NHS Trust", service_requirement: "Security systems", incumbent: "Mitie Security Limited", commercial_value: "", contract_lifecycle: "2024-09-01 to 2027-08-31", procurement_route: "Not published", timing: "", why_it_matters: "Title names both the system and the service.", missing_information: ["Procurement route."], next_action: "" },
  evidence: [{ source_revision_id: 1, source_url: "https://www.contractsfinder.service.gov.uk/Notice/1", source: "Contracts Finder", record_key: "1", published_at: "2024-08-07" }],
};
const summary = {
  opportunities: 1, by_category: { contract_defence: 1 }, by_tier: { 1: 1 }, renewals_within_months: { 3: 0, 6: 0, 12: 1, 18: 1 }, value: { estimated_annualised: 240382, estimated_annualised_core_only: 240382, unknown_value_renewals: 0 },
  find_a_tender_unbroken_from: "2022-10-10", health: [{ source_key: "public_contracts_scotland", status: "failing", last_success_at: null }], limits: ["Private-sector contracts are not covered."],
};

const dossier = {
  id: 1, opportunity_id: 1, model: "claude-opus-5-5", created_at: "2026-11-04T20:00:00+00:00",
  headline: "Open a retention conversation with the estates lead before the 2027 re-tender.", summary: "The trust is consolidating its estate.",
  recommendation: { stance: "pursue", rationale: "Mitie holds the contract and the term ends in 2027." },
  buyer: { overview: "A mental health trust.", estate: "Several secure sites.", priorities: ["Estate consolidation"], developments: [{ date: "2026", development: "New estates strategy", relevance: "Changes the site list.", source_url: "https://www.example.nhs.uk/strategy" }] },
  contract: { position: "In term", incumbent: "Mitie Security Limited", timeline: "Ends 31 August 2027", route: "Not published" },
  signals: [], decision_roles: [{ role: "Director of Estates", why: "Owns the budget." }], win_strategy: { angle: "Continuity through the consolidation.", themes: ["Continuity"], proof_points: [] },
  risks: [], questions: ["Which sites stay in scope?"], next_steps: [], unknowns: [], sources: [{ title: "Estates strategy", url: "https://www.example.nhs.uk/strategy" }],
};

test("sales team can filter, open, research and add a lead to the pipeline", async ({ page }) => {
  let promoted = 0;
  let researched = 0;
  const queries: string[] = [];
  await page.route("**/api/market-network/opportunities**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/summary")) return route.fulfill({ json: summary });
    if (url.pathname.endsWith("/promote")) { promoted += 1; return route.fulfill({ json: { opportunity_id: 9, created: true } }); }
    if (url.pathname.endsWith("/dossier")) {
      if (route.request().method() === "POST") { researched += 1; return route.fulfill({ json: { dossier } }); }
      return route.fulfill({ json: { dossier: null } });
    }
    queries.push(url.search);
    return route.fulfill({ json: { items: [{ id: 1, review_state: "unreviewed", suggestion }], total: 1 } });
  });
  await page.goto("/?view=radar");
  await expect(page.getByRole("heading", { name: "Opportunity Finder" })).toBeVisible();
  await expect(page.getByText("Public Contracts Scotland is failing", { exact: false })).toBeVisible();
  await page.getByRole("group", { name: "Opportunity type" }).getByRole("button", { name: /Contract defence/ }).click();
  await expect.poll(() => queries.some(x => x.includes("category=contract_defence"))).toBe(true);
  await page.getByRole("button", { name: /West London NHS Trust/ }).click();
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByText("Escalate to the account lead for retention planning.")).toBeVisible();
  await detail.getByRole("tab", { name: "Deep research" }).click();
  await detail.getByRole("button", { name: "Run deep research" }).click();
  await expect(detail.getByText(dossier.headline)).toBeVisible();
  await expect(detail.getByRole("link", { name: /Estates strategy/ })).toBeVisible();
  expect(researched).toBe(1);
  await detail.getByRole("button", { name: "Add to pipeline" }).click();
  await expect.poll(() => promoted).toBe(1);
  await expect(detail.getByRole("button", { name: "In your pipeline" })).toBeVisible();
});
