import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Contract Atlas in a single-user local install, on the fictional market (backend/app/services/atlas_fixtures.py).
test("a local install answers who holds the work and spends nothing in demo mode", async ({ page }) => {
  await page.goto("/?view=find");
  await page.getByRole("group", { name: "Discover mode" }).getByRole("button", { name: "Contract Atlas" }).click();
  await expect(page).toHaveURL(/mode=atlas/);
  await page.getByLabel("Contractor or customer").fill("Brightwater");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const contractors = page.getByRole("region", { name: "Contractors" });
  await expect(contractors.getByRole("button")).toHaveCount(3); // one name with two company numbers, and a lookalike, kept apart
  await contractors.getByRole("button", { name: /Companies House 11122233/ }).click();
  const record = page.getByRole("article", { name: "Contractor BRIGHTWATER SECURITY LTD" });
  await expect(record.getByRole("note").first()).toContainText("more than one company number");
  await expect(record).toContainText("Intruder alarms and monitoring");
  await record.getByRole("button", { name: "Research published customers" }).click();
  await expect(page.getByText("Web research is switched off in demo mode")).toBeVisible(); // no paid call is made here
  const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);

  // A customer with no current published supplier says so plainly.
  await page.getByLabel("Contractor or customer").fill("Calder Valley");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("region", { name: "Customers" }).getByRole("button", { name: /Calder Valley Council/ }).click();
  await expect(page.getByRole("article", { name: "Customer Calder Valley Council" })).toContainText("Current supplier not publicly established");
});
