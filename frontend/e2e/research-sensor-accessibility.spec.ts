import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("expanded evidence and attendance tools remain legible on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/virtual-sensors/false-alarms**", (route) => route.fulfill({ json: { total: 0, items: [], period_start: null, period_end: null, source_url: "https://data.london.gov.uk/dataset/example", limitations: [] } }));
  await page.route("**/api/evidence-observations/accounts**", (route) => route.fulfill({ json: { items: [], total: 0 } }));
  await page.goto("/?view=discover");
  await page.getByText("Explore London fire-alarm attendances", { exact: true }).click();
  await page.getByText("Review your evidence inbox", { exact: true }).click();
  await expect(page.getByRole("region", { name: "False alarm sensor" }).getByText("No matching attendance patterns")).toBeVisible();
  await expect(page.getByRole("region", { name: "Evidence inbox" })).toBeVisible();
  await page.getByRole("region", { name: "Evidence inbox" }).getByRole("button", { name: "Add an observation" }).click();
  const scan = await new AxeBuilder({ page }).include('[aria-label="False alarm sensor"]').include('[aria-label="Evidence inbox"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});
