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

test("sales team can filter, open and promote a radar opportunity", async ({ page }) => {
  let promoted = 0;
  const queries: string[] = [];
  await page.route("**/api/market-network/opportunities**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/summary")) return route.fulfill({ json: summary });
    if (url.pathname.endsWith("/promote")) { promoted += 1; return route.fulfill({ json: { opportunity_id: 9, created: true } }); }
    queries.push(url.search);
    return route.fulfill({ json: { items: [{ id: 1, review_state: "unreviewed", suggestion }], total: 1 } });
  });
  await page.goto("/?view=radar");
  await expect(page.getByRole("heading", { name: "Renewal Radar" })).toBeVisible();
  await expect(page.getByText("Needs attention: Public Contracts Scotland is failing.")).toBeVisible();
  await page.getByRole("button", { name: "Contract defence" }).click();
  await expect.poll(() => queries.some(x => x.includes("category=contract_defence"))).toBe(true);
  await page.getByText("Security Systems Maintenance at Broadmoor Hospital").click();
  await expect(page.getByText("Escalate to the account lead for retention planning.")).toBeVisible();
  await page.getByRole("button", { name: "Add to pursuits" }).click();
  await expect.poll(() => promoted).toBe(1);
});
