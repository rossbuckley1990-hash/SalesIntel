import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Each rep's own sales target, on fictional records: set it with the patch form, see what it means, and give the rep a deal
// that counts towards it. No figure or period is built in; the numbers here are the test's own.
const API = "http://127.0.0.1:8011/api/si";
const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text }).first()).toBeVisible();
const shot = (page: Page, name: string) => page.screenshot({ animations: "disabled", path: `../docs/saas/screenshots/${name}`, mask: [page.locator(".m-workspace-name")], maskColor: "#e4e7ec" });

test("a rep sets their own target, sees what it means, and a deal counts towards it", async ({ page }) => {
  const start = await (await page.request.get(`${API}/patch/reps`)).json();
  for (const r of start.reps) await page.request.delete(`${API}/patch/reps/${encodeURIComponent(r.name)}`);

  // The target is set with the patch, and is the rep's own.
  await page.goto("/?view=today");
  const brief = page.getByRole("region", { name: "Patch brief" });
  await brief.getByRole("button", { name: "Set up your patch" }).click();
  const form = brief.getByRole("form", { name: "Patch" });
  await form.getByLabel("Whose patch is this?").fill("Sam North");
  await form.getByLabel("Amount (£)").fill("250000");
  await expect(form.getByLabel("Period starts")).not.toHaveValue("");  // starts on the first of this month unless changed
  await form.getByLabel("Average deal value (£, a planning figure)").fill("50000");
  await form.getByLabel("Qualified opportunities for each win").fill("4");
  await form.getByRole("button", { name: "Save and show the five" }).click();
  await toast(page, "Patch saved.");

  const target = brief.getByRole("region", { name: "Sales target" });
  await expect(target.getByRole("heading", { name: "Sam North's target: £250,000 new annual contract value" })).toBeVisible();
  await expect(target).toContainText("Signed in the period£0");
  await expect(target).toContainText("Still to sign£250,000");
  await expect(target).toContainText("About 5 wins from 20 qualified opportunities: 20 more to find");
  await expect(target).toContainText("From your planning figures. A plan, not a forecast.");
  await expect(target.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0);
  await target.scrollIntoViewIfNeeded();
  await shot(page, "40-rep-target-desktop.png");
  const scan = await new AxeBuilder({ page }).include('[aria-label="Patch brief"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);

  // A deal created while Sam's patch is on screen counts towards Sam; its annual value is recorded on the deal.
  const { account_id: id } = await (await page.request.post(`${API}/accounts`, { data: { name: "Example Target Housing", sector: "Housing" } })).json();
  const deal = await (await page.request.post(`${API}/accounts/${id}/deals`, { data: { qualification: { requirement: "Annual servicing at 12 sheltered schemes" } } })).json();
  expect(deal.owner_rep).toBe("Sam North");
  await page.goto(`/?view=deals&deal=${deal.id}`);
  await expect(page.getByRole("combobox", { name: "Owner" })).toHaveValue("Sam North");
  await page.getByRole("button", { name: "Record values" }).click();
  await page.getByLabel("Annual value (£ a year)").fill("60000");
  await page.getByRole("button", { name: "Save values" }).click();
  await toast(page, "Values recorded.");
  await expect(page.getByText("£60,000 a year").first()).toBeVisible();
  await expect(page.getByText("£60,000 a year (your estimate).")).toBeVisible();  // "Can we win this?" follows the recorded value
  await shot(page, "41-deal-owner-and-value-desktop.png");

  // Back on Today, the open deal is on Sam's target, and the plan counts it.
  await page.goto("/?view=today");
  await expect(target).toContainText("Open, qualified£60,000");
  await expect(target).toContainText("1 deal");
  await expect(target).toContainText("19 more to find");

  // A phone: the target fits.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=today");
  await expect(target).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await target.scrollIntoViewIfNeeded();
  await shot(page, "42-rep-target-mobile.png");

  // Left as found: the rep is removed, so later tests see no rep and no owner.
  await page.request.delete(`${API}/patch/reps/${encodeURIComponent("Sam North")}`);
});
