import { expect, test } from "@playwright/test";

test("Discover keeps the research journey prominent and additional tools available by keyboard", async ({ page }) => {
  await page.goto("/?view=discover");
  await expect(page.getByRole("region", { name: "Public opportunity research" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Saved research workspace" })).toBeVisible();
  const internal = page.getByText("Search internal records", { exact: true });
  const disclosure = internal.locator("xpath=ancestor::summary");
  await expect(page.getByLabel("Commercial question")).toBeHidden();
  await disclosure.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Commercial question")).toBeVisible();
  await page.getByLabel("Commercial question").fill("Find existing healthcare opportunities");
  await page.keyboard.press("Shift+Tab");
  await disclosure.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Commercial question")).toBeHidden();
  await disclosure.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Commercial question")).toHaveValue("Find existing healthcare opportunities");
  await page.getByText("Review your evidence inbox", { exact: true }).click();
  await expect(page.getByRole("region", { name: "Evidence inbox" })).toBeVisible();
});

test("additional research tools remain readable on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=discover");
  const tools = page.getByRole("region", { name: "More ways to investigate" });
  await expect(tools).toBeVisible();
  await page.getByText("Search internal records", { exact: true }).click();
  await expect(page.getByLabel("Commercial question")).toBeVisible();
  const bounds = await tools.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(391);
});

test("tablet discovery heading aligns with the research workspace", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("/?view=discover");
  const heading = await page.getByRole("heading", { name: "Discover opportunities" }).boundingBox();
  const research = await page.getByRole("region", { name: "Public opportunity research" }).boundingBox();
  expect(heading).not.toBeNull();
  expect(research).not.toBeNull();
  expect(Math.abs(heading!.x - research!.x)).toBeLessThanOrEqual(2);
});
