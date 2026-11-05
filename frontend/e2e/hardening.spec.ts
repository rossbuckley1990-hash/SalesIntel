import { expect, test } from "@playwright/test";

// Synthetic demo database (see backend/scripts/salesintel_fixtures.py). Set-up goes through the
// real API; the checks are what a salesperson sees.
const api = "http://127.0.0.1:8011/api/si";

test("an approval superseded by a scope change is shown and blocks winning", async ({ page, request }) => {
  const lead = (await (await request.get(`${api}/discover?q=sample%20borough`)).json()).items[0];
  const account = (await (await request.post(`${api}/discover/${lead.key}/account`, { data: {} })).json()).account_id;
  const deal = (await (await request.post(`${api}/accounts/${account}/deals`, { data: { source_key: lead.key, services: ["cctv"], qualification: { requirement: "CCTV maintenance" } } })).json()).id;
  await request.put(`${api}/deals/${deal}/scope`, { data: { entries: [
    { service: "cctv", field: "cameras", value: 40, basis: "surveyed" }, { service: "cctv", field: "recorders", value: 2, basis: "surveyed" },
    { service: "cctv", field: "visits_per_year", value: 2, basis: "customer_stated" }] } });
  await request.post(`${api}/deals/${deal}/quote`, { data: { rates: { "cctv.cameras": "12.50", "cctv.recorders": "95", "cctv.visits_per_year": "280.005" } } });
  expect((await (await request.post(`${api}/deals/${deal}/quote/approve`, { data: { reviewer: "Pat Manager" } })).json()).quote.status).toBe("approved");

  await page.goto(`/?view=deals&deal=${deal}`);
  await expect(page.getByText("Version 1 approved by Pat Manager")).toBeVisible();
  await expect(page.getByText("£500.00")).toBeVisible(); // 40 × £12.50, exact
  await page.getByLabel("Cameras", { exact: true }).fill("44");
  await page.getByRole("button", { name: "Save scope" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Scope changed after approval" })).toBeVisible();
  await expect(page.getByText("Approval superseded")).toBeVisible();
  await page.getByRole("button", { name: "Won" }).click();
  await page.getByLabel("Why did we win?").fill("Signed");
  await page.getByRole("button", { name: "Confirm won" }).click();
  await expect(page.locator(".m-toast").filter({ hasText: /Approve the current quotation/ })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Approval superseded")).toBeVisible();
  expect((await (await request.get(`${api}/deals/${deal}`)).json()).stage).toBe("qualify");
});

test("a draft to someone who opted out is suspended and cannot be approved", async ({ page, request }) => {
  const account = (await (await request.post(`${api}/accounts`, { data: { name: "Suppression Check Ltd" } })).json()).account_id;
  const contact = (await (await request.post(`${api}/accounts/${account}/contacts`, { data: { name: "Jo Example", role: "Assets", email: "jo@example-housing.example" } })).json()).id;
  const draft = (await (await request.post(`${api}/accounts/${account}/drafts`, { data: { subject: "Hello", body: "Dear Jo, hello. Regards, Alex, Regional Fire", contact_id: contact } })).json()).id;
  expect((await (await request.post(`${api}/drafts/${draft}/approve`)).json()).status).toBe("approved");
  await request.patch(`${api}/contacts/${contact}`, { data: { status: "do_not_contact" } });

  await page.goto(`/?view=engage&account=${account}&draft=${draft}`);
  await expect(page.getByText("Suspended: recipient opted out")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();
  await expect(page.getByText("The recipient asked not to be contacted. This draft cannot be sent.")).toBeVisible();
  await expect(page.getByText("Sent it from your own email?")).toHaveCount(0);
  const today = await (await request.get(`${api}/today`)).json();
  expect(today.queue.some((q: { draft_id?: number }) => q.draft_id === draft)).toBe(false);
});
