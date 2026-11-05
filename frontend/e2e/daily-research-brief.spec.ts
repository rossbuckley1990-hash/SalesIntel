import { expect, test } from "@playwright/test";

const cors = { "access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-methods": "GET,PATCH,OPTIONS", "access-control-allow-headers": "content-type" };

test("Home shows the research briefing with due follow-ups and recent leads", async ({ page }) => {
  const actions = [
    { id: 1, lead_id: 17, organisation: "Example Trust", headline: "Review maintenance", text: "Confirm current arrangements", status: "open", due_date: null },
    { id: 2, lead_id: 17, organisation: "Example Trust", headline: "Review maintenance", text: "Check published estate evidence", status: "open", due_date: "2026-11-03" },
    { id: 3, lead_id: 17, organisation: "Example Trust", headline: "Review maintenance", text: "Review the source", status: "open", due_date: "2026-10-30" },
    { id: 4, lead_id: 17, organisation: "Example Trust", headline: "Review maintenance", text: "Ask about ownership", status: "open", due_date: "2026-12-01" },
  ];
  const lead = { id: 17, organisation: "Example Trust", headline: "Review maintenance arrangements", location: "Yorkshire", created_at: "2026-10-28T12:00:00Z", opportunity: { thesis: "Estate changes may warrant a conversation.", verification_action: "Confirm the current service arrangement." } };
  let updated = 0;
  await page.route("**/api/research-dossiers/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (route.request().method() === "PATCH") { updated += 1; return route.fulfill({ headers: cors, json: {} }); }
    if (route.request().url().includes("/actions?")) return route.fulfill({ headers: cors, json: { items: actions, total: 4 } });
    if (route.request().url().includes("/leads?")) return route.fulfill({ headers: cors, json: { items: [lead], total: 1 } });
    return route.fulfill({ headers: cors, json: { items: [], total: 0 } });
  });
  await page.goto("/?view=today");
  const briefing = page.getByRole("region", { name: "Research briefing" });
  await expect(briefing.getByText("Review the source")).toBeVisible();
  await expect(briefing.getByText("Confirm current arrangements")).not.toBeVisible();
  await expect(briefing.getByText("Estate changes may warrant a conversation.")).toBeVisible();
  await expect(briefing.getByText("Confirm the current service arrangement.")).toBeVisible();
  await expect(briefing.getByText(/not a ranking/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Act on these first" })).toBeVisible();
  await briefing.getByRole("button", { name: "Show 4 loaded follow-ups" }).click();
  await expect(briefing.getByText("Confirm current arrangements")).toBeVisible();
  await briefing.getByRole("article").filter({ hasText: "Review the source" }).getByRole("button", { name: "Mark done" }).click();
  await expect(briefing.getByText("Review the source")).not.toBeVisible();
  expect(updated).toBe(1);
});
