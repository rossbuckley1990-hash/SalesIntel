import { expect, test } from "@playwright/test";

test("reviews an attendance pattern, its source and public research without treating it as an established buyer", async ({ page }) => {
  const site = { uprn: "100012345678", property_type: "Hospital", postcode_district: "E1", attendances: 5,
    first_seen: "2026-01-02", last_seen: "2026-08-02", comparison: { cohort_sites: 20, mean_attendances: 1.5 },
    research_brief: "Investigate reported fire-alarm attendances; an occupier and buying intention are not established." };
  const context = { period_start: "2025-10-01", period_end: "2026-09-30", source_url: "https://data.london.gov.uk/dataset/example", limitations: ["Attendances do not establish a fault."], snapshot: { source_file: "incident-data.xlsx", sha256: "abc123", imported_at: "2026-10-01T12:00:00Z", acquisition_method: "local_file", retrieved_at: null, records_imported: 27 } };
  await page.route("**/api/virtual-sensors/false-alarms**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/inspection-context")) return route.fulfill({ json: { snapshot_available: true, source_url: "https://data.london.gov.uk/inspections", matches: [{ organisation_name: "Example NHS Trust", site_name: "Example Hospital", site_reference_url: "https://example.com/historical", site_reference_period: "2025/26", inspection_address: "Example Hospital, Block A", postcode: "E1 1AA", completed_on: "2025-03-01", reason_or_outcome: "Audit", source_file: "inspection.xlsx" }], limitations: ["Candidate match may refer to a different building or block."] } });
    if (path.endsWith("/research")) {
      expect(route.request().postDataJSON()).toEqual({ property_type: "Hospital" });
      return route.fulfill({ json: { site, site_references: [{ uprn: site.uprn, organisation_id: "nhs-ods:TEST", organisation_name: "Example NHS Trust", site_name: "Example Hospital", postcode: "E1 1AA", source_period: "2025/26", source_url: "https://example.com/historical" }], research: { identity_status: "unknown", organisation: "", site_name: "", identity_explanation: "The current occupier could not be confirmed.", identity_sources: [], inferred_maintenance_need: "An alarm review may be useful, subject to verification.", contact_name: "", contact_role: "Estates team", contact_sources: [], engagement: "Ask who manages alarm maintenance.", limitations: ["The historic reference is not proof of the current occupier."] } } });
    }
    if (path.endsWith(site.uprn)) return route.fulfill({ json: { site, incidents: [{ incident_number: "INC-1", incident_date: "2026-08-02", stop_code_description: "AFA", address_qualifier: "Correct incident location" }], ...context } });
    return route.fulfill({ json: { total: 1, items: [site], ...context } });
  });
  await page.goto("/?view=discover");
  await page.getByText("Explore London fire-alarm attendances", { exact: true }).click();
  const sensor = page.getByRole("region", { name: "False alarm sensor" });
  await expect(sensor.getByText(/UPRN identifies a property, not its occupier/)).toBeVisible();
  await expect(sensor.getByText(/acquisition: local_file · retrieved: unknown/)).toBeVisible();
  await sensor.getByRole("button", { name: /Property UPRN 100012345678/ }).click();
  await expect(sensor.getByText("Correct incident location", { exact: false })).toBeVisible();
  await expect(sensor.getByText(/Peer mean: 1.5/)).toBeVisible();
  await sensor.getByRole("button", { name: "Check related inspections" }).click();
  await expect(sensor.getByText("Example Hospital, Block A", { exact: false })).toBeVisible();
  await expect(sensor.getByText(/different building or block/).first()).toBeVisible();
  await expect(sensor.getByRole("link", { name: "NHS site reference" })).toHaveAttribute("href", "https://example.com/historical");
  await sensor.getByRole("button", { name: "Research this property with AI" }).click();
  await expect(sensor.getByText(/The current occupier could not be confirmed/)).toBeVisible();
  await expect(sensor.getByText(/historic reference is not proof/)).toBeVisible();
  await expect(sensor.getByRole("link", { name: "Source", exact: true })).toHaveAttribute("href", "https://example.com/historical");
});

test("reports an empty dataset and a failed exact-property lookup without inventing a site", async ({ page }) => {
  await page.route("**/api/virtual-sensors/false-alarms**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/123")) return route.fulfill({ status: 404, json: { detail: "No eligible observed site for that UPRN and property type." } });
    return route.fulfill({ json: { total: 0, items: [], period_start: null, period_end: null, source_url: "https://data.london.gov.uk/dataset/example", limitations: [] } });
  });
  await page.goto("/?view=discover");
  await page.getByText("Explore London fire-alarm attendances", { exact: true }).click();
  const sensor = page.getByRole("region", { name: "False alarm sensor" });
  await expect(sensor.getByText("No dataset period is available", { exact: false })).toBeVisible();
  await expect(sensor.getByText("No matching attendance patterns")).toBeVisible();
  await sensor.getByLabel("Look up an exact UPRN").fill("123");
  await sensor.getByRole("button", { name: "Look up property" }).click();
  await expect(sensor.getByRole("alert")).toContainText("No eligible observed site");
  await expect(sensor.getByRole("button", { name: "Research this property with AI" })).toHaveCount(0);
});
