import { expect, test } from "@playwright/test";

test("reviewer can add and batch import sourced observations without creating opportunities", async ({ page, request }) => {
  const before = await (await request.get("http://127.0.0.1:8011/api/living/workspace")).json();
  await page.goto("/?view=discover");
  await page.getByText("Review your evidence inbox", { exact: true }).click();
  const inbox = page.getByRole("region", { name: "Evidence inbox" });
  await expect(inbox.getByText(/not live UK-wide monitoring/)).toBeVisible();
  await inbox.getByRole("button", { name: "Add an observation" }).click();
  await inbox.getByLabel("Organisation ID").fill("DEMO:review-test");
  await inbox.getByLabel("Organisation name").fill("Example Estates Ltd");
  await inbox.getByLabel("Site, if known").fill("York site");
  await inbox.getByLabel("Signal type").selectOption("maintenance");
  await inbox.getByLabel("Source title").fill("Published maintenance note");
  await inbox.getByLabel("Stable source reference").fill("note-1");
  await inbox.getByLabel("Source URL").fill("https://example.com/note-1");
  await inbox.getByLabel("Published date, if known").fill("2026-10-01");
  await inbox.getByLabel("Observed statement").fill("A maintenance visit was scheduled.");
  await inbox.getByRole("button", { name: "Save observation" }).click();
  await expect(inbox.getByRole("status")).toContainText("1 observation saved");
  await inbox.getByRole("button", { name: "Import a batch" }).click();
  await inbox.getByLabel("Observation JSON").fill(JSON.stringify([{
    organisation_id: "DEMO:review-test", organisation_name: "Example Estates Ltd", site: "York site", category: "customer_feedback",
    observed_statement: "A review reports a service concern.", source_title: "Customer review", source_reference: "review-2", source_url: "https://example.com/review-2", retrieved_at: "2026-10-28T12:00:00Z",
  }]));
  await inbox.getByRole("button", { name: "Import batch" }).click();
  await expect(inbox.getByRole("status")).toContainText("1 observation saved");
  await inbox.getByRole("button", { name: /Example Estates Ltd/ }).click();
  await expect(inbox.getByText("A maintenance visit was scheduled.", { exact: true })).toBeVisible();
  await expect(inbox.getByText("A review reports a service concern.", { exact: true })).toBeVisible();
  await expect(inbox.getByText(/Check identity, relevance and source reliability/)).toBeVisible();
  await expect(inbox.getByRole("link", { name: "View source" })).toHaveCount(2);
  const after = await (await request.get("http://127.0.0.1:8011/api/living/workspace")).json();
  expect(after.opportunities).toHaveLength(before.opportunities.length);
});

test("shows rule patterns and explicitly requested AI hypotheses with their evidence and unknowns", async ({ page }) => {
  const organisationId = "TEST:inference";
  const observations = [
    { id: 101, organisation_id: organisationId, organisation_name: "Example Estate", site: "York", category: "maintenance", observed_statement: "An inspection programme is scheduled.", source_title: "Programme notice", source_reference: "notice-1", source_url: "https://example.com/notice", published_at: "2026-09-01", observed_at: null, retrieved_at: "2026-10-01T12:00:00Z" },
    { id: 102, organisation_id: organisationId, organisation_name: "Example Estate", site: "York", category: "customer_feedback", observed_statement: "A resident reported delays.", source_title: "Feedback", source_reference: "feedback-2", source_url: "https://example.com/feedback", published_at: "2026-09-02", observed_at: null, retrieved_at: "2026-10-01T12:00:00Z" },
    { id: 103, organisation_id: organisationId, organisation_name: "Example Estate", site: "York", category: "other", observed_statement: "The organisation reports resolving the issue.", source_title: "Update", source_reference: "update-3", source_url: "https://example.com/update", published_at: "2026-09-03", observed_at: null, retrieved_at: "2026-10-01T12:00:00Z" },
  ];
  await page.route("**/api/evidence-observations/accounts**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/ai-hypotheses")) {
      expect(route.request().method()).toBe("POST");
      expect(route.request().postDataJSON()).toEqual({ site: "York", observation_ids: [102, 103] });
      return route.fulfill({ json: { organisation_id: organisationId, site: "York", observations, hypotheses: [{ title: "Possible delay to investigate", explanation: "A reported delay could merit a discussion; other explanations remain possible.", supporting_observation_ids: [102], counter_observation_ids: [103], unknowns: ["Supplier and contract scope are unknown."], question: "How are service delays resolved?" }], limitations: ["Source facts have not been independently verified."] } });
    }
    if (url.pathname.endsWith("/hypotheses")) return route.fulfill({ json: { organisation_id: organisationId, total_observations: 3, analysed_observations: 3, observations, sites: [{ site: "York", hypotheses: [{ title: "Possible customer experience to investigate", explanation: "These observations may merit a discussion.", observation_ids: [101, 102], question: "How is service experience assessed?" }] }], limitations: ["Different URLs do not establish independent sources."] } });
    if (url.pathname.endsWith("/accounts")) return route.fulfill({ json: { items: [{ organisation_id: organisationId, organisation_name: "Example Estate", observation_count: 3 }], total: 1 } });
    return route.fulfill({ json: { organisation_id: organisationId, organisation_name: "Example Estate", observations, total: 3 } });
  });
  await page.goto("/?view=discover");
  await page.getByText("Review your evidence inbox", { exact: true }).click();
  const inbox = page.getByRole("region", { name: "Evidence inbox" });
  await inbox.getByRole("button", { name: /Example Estate/ }).click();
  const patterns = inbox.getByRole("region", { name: "Patterns to investigate" });
  await expect(patterns.getByText("Rule patterns do not use AI.", { exact: false })).toBeVisible();
  await expect(patterns.getByText("Possible customer experience to investigate")).toBeVisible();
  await expect(patterns.getByText("An inspection programme is scheduled.", { exact: true })).toBeVisible();
  await expect(patterns.getByText("Different URLs do not establish independent sources.")).toBeVisible();
  await patterns.getByLabel(/A resident reported delays/).check();
  await patterns.getByLabel(/The organisation reports resolving the issue/).check();
  await patterns.getByRole("button", { name: "Analyse selected observations with AI" }).click();
  await expect(patterns.getByText("Possible delay to investigate")).toBeVisible();
  await expect(patterns.getByText("The organisation reports resolving the issue.", { exact: true })).toBeVisible();
  await expect(patterns.getByText("Supplier and contract scope are unknown.")).toBeVisible();
  await expect(patterns.getByText("How are service delays resolved?")).toBeVisible();
});
