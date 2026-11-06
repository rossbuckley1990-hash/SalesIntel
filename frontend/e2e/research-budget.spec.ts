import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// A local install has no Team page. Its owner approves live research spending from the menu, as a hard ceiling.
test("the owner of a local install approves a research budget from the menu", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Research budget" }).click();
  await expect(page).toHaveURL(/view=budget/);
  const panel = page.getByRole("region", { name: "Research budget" });
  await expect(panel).toContainText("No budget approved");
  await panel.getByLabel("Budget to add").fill("20");
  await panel.getByLabel("Budget purpose").fill("First live investigations");
  await panel.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Research budget approved.")).toBeVisible();
  await expect(panel.getByText("$20.00").first()).toBeVisible();
  await expect(panel).not.toContainText("No budget approved");
  const scan = await new AxeBuilder({ page }).include('[aria-label="Research budget"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);
});
