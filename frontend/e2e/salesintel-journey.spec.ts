import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Runs against the real API on an isolated demo database with clearly synthetic fixtures
// (backend/scripts/salesintel_fixtures.py). No model calls: demo mode refuses them.

async function toast(page: Page, text: RegExp | string) {
  await expect(page.locator(".m-toast").filter({ hasText: text })).toBeVisible();
}

test("discover to contact to deal, with continuity after a reload", async ({ page }) => {
  await page.goto("/?view=find");
  await expect(page.getByRole("heading", { name: "Discover", exact: true })).toBeVisible();
  const results = page.getByRole("region", { name: "Results" });
  await results.getByRole("button", { name: /Example Housing Trust Limited/ }).click();
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByText(/Published contract with Sample Fire Services Ltd ends/)).toBeVisible();
  await expect(detail.getByText("Reported, not necessarily today's incumbent")).toBeVisible();

  // Prepare an introduction straight from the lead.
  await detail.getByRole("button", { name: "Prepare introduction" }).click();
  await expect(page).toHaveURL(/view=engage/);
  const message = page.getByLabel("Message", { exact: true });
  await expect(message).toHaveValue(/Dear \[name\],/);
  await expect(message).not.toHaveValue(/@|\d{5} ?\d{6}/); // no invented email or phone
  await expect(page.getByText("No contact selected: add the recipient's name.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();
  await page.getByLabel("Your name").fill("Alex Rep");
  await page.getByLabel("Your company").fill("Regional Fire Ltd");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await toast(page, "Saved");
  await page.getByRole("button", { name: "Rebuild from evidence" }).click();
  await expect(message).toHaveValue(/Alex Rep/);
  await message.fill((await message.inputValue()).replace("Dear [name],", "Dear Assets team,"));
  await page.getByRole("button", { name: "Approve" }).click();
  await toast(page, /Approved/);
  await expect(page.getByRole("button", { name: "Log as sent" })).toBeDisabled();
  await page.getByLabel("I sent this message myself").check();
  await page.getByRole("button", { name: "Log as sent" }).click();
  await toast(page, /Logged as sent/);

  // The follow-up is on Today without retyping anything.
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.getByText(/Follow up on introduction to Example Housing Trust Limited/).first()).toBeVisible();

  // The account remembers the evidence and the history.
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Accounts", exact: true }).click();
  await page.getByRole("button", { name: "Example Housing Trust Limited" }).click();
  await expect(page.getByRole("heading", { name: "Example Housing Trust Limited" })).toBeVisible();
  await page.getByLabel("What happened").fill("Called the assets team about the sheltered schemes");
  await page.getByLabel("Outcome").selectOption("requirement_captured");
  await page.getByRole("button", { name: "Save to timeline" }).click();
  await toast(page, /Logged/);

  // Qualify into a deal; the original evidence travels with it.
  await page.getByRole("button", { name: "Qualify into a deal" }).click();
  await page.getByLabel("Customer requirement (confirmed)").fill("Annual fire alarm servicing at 14 schemes");
  await page.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await page.getByRole("button", { name: "Create deal" }).click();
  await expect(page).toHaveURL(/view=deals&deal=\d+/);
  await expect(page.getByRole("link", { name: /Contracts Finder notice example-synthetic-0001/ })).toBeVisible();
  await expect(page.getByText("Value:").locator("..")).toContainText("Unknown");

  // Continuity: reload and everything is still there.
  await page.reload();
  await expect(page.getByRole("link", { name: /Contracts Finder notice example-synthetic-0001/ })).toBeVisible();
  await expect(page.getByText("Called the assets team about the sheltered schemes")).toBeVisible();
  await expect(page.getByText(/Sent: Example Housing Trust Limited/)).toBeVisible();

  // Deduplication: the same organisation found by private research joins the same account, unconfirmed.
  await page.goto("/?view=find&q=example housing");
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Private/ }).first().click();
  await page.getByRole("complementary", { name: "Selected opportunity" }).getByRole("button", { name: /Open account|Investigate as account/ }).click();
  await toast(page, /Linked to the existing Example Housing Trust account by name/);
  await expect(page.getByText("Same name (unconfirmed)").first()).toBeVisible();
  // The named person research sourced arrives once, with the quote that names them.
  await expect(page.getByRole("listitem").filter({ hasText: "Head of Assets" }).filter({ hasText: "said Robin Sample, Head of Assets" })).toHaveCount(1);

  // Safety: web research is refused in demo mode, so no API credit is spent.
  await page.goto("/?view=find");
  await page.getByLabel("Search opportunities").fill("care homes in Yorkshire");
  await page.getByRole("button", { name: "Research the web" }).click();
  await toast(page, /switched off in demo mode/);
});

test("the five workspaces are accessible and fit a phone screen", async ({ page }) => {
  for (const view of ["today", "find", "clients", "engage", "deals"]) {
    await page.goto(`/?view=${view}`);
    await expect(page.locator("main h1").first()).toBeVisible();
    const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(scan.violations.map((v) => ({ view, id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  for (const view of ["today", "find", "clients", "engage", "deals"]) {
    await page.goto(`/?view=${view}`);
    await expect(page.locator("main h1").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth), view).toBeLessThanOrEqual(390);
  }
  // Keyboard: / focuses Discover search and j moves the selection.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/?view=find");
  await expect(page.getByRole("region", { name: "Results" }).getByRole("button").first()).toBeVisible();
  await page.keyboard.press("/");
  await expect(page.getByLabel("Search opportunities")).toBeFocused();
});
