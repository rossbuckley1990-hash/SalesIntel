import { expect, test, type Browser, type Page } from "@playwright/test";

// The Living Opportunity in hosted mode, with research replayed offline (no network, no credit). The key question is
// researched from the Action Dock in two interactions; what the sources do not say stays unknown, and the next move
// changes to asking the customer. Everything survives a reload, and another company sees none of it.

async function signUp(browser: Browser, email: string, name: string, company: string) {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Company name").fill(company);
  await page.getByRole("button", { name: "Create workspace" }).click();
  return page;
}
const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name, exact: true }).click();

test("research the key question from the Action Dock: cost shown, answer kept, not-found stays not found", async ({ browser }) => {
  const page = await signUp(browser, "rita.research@epsilon-living.example", "Rita Research", "Epsilon Fire Ltd");
  await nav(page, "Discover");
  let clicks = 0;
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Example Housing Trust Limited/ }).click(); clicks++;
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  const dock = detail.getByRole("region", { name: "Next move" });
  await expect(dock).toContainText("Research: Will the buyer extend, re-tender or call off");
  await expect(dock).toContainText("Up to $1.20 from the approved research budget");
  await expect(dock).toContainText("It saves this as an account first");
  await dock.getByRole("button", { name: "Research the key question" }).click(); clicks++;
  expect(clicks).toBeLessThanOrEqual(2); // targeted research within two interactions
  await expect(dock.getByRole("button", { name: /Open the full account/ })).toBeVisible(); // saved as an account on the way

  // The replayed sources do not say how the buyer will re-procure: that is reported as not published, never guessed.
  const questions = detail.getByRole("region", { name: "Questions that decide this opportunity" });
  const route = questions.getByRole("listitem").filter({ hasText: "Will the buyer extend, re-tender or call off" });
  await expect(route).toContainText("Not published: ask the customer", { timeout: 30000 });
  await expect(route.getByRole("button", { name: "Record the customer’s answer" })).toBeVisible();
  await expect(detail.getByRole("region", { name: "Evidence, newest first" })).toContainText("Research: Will the buyer extend");
  await expect(dock).not.toContainText("Research: Will the buyer extend"); // the next move has moved on

  // Durable: after a reload the answer, the account and the next move are all still there.
  await page.reload();
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Example Housing Trust Limited/ }).click();
  await expect(detail.getByRole("region", { name: "Questions that decide this opportunity" }).getByRole("listitem")
    .filter({ hasText: "Will the buyer extend, re-tender or call off" })).toContainText("Not published: ask the customer");
  await expect(detail.getByRole("region", { name: "Deal story" })).toContainText("Researched: Route to market");

  // Another company sees the public notice, but none of this workspace's research or account.
  const rival = await signUp(browser, "ravi.rival@zeta-living.example", "Ravi Rival", "Zeta Security Ltd");
  await nav(rival, "Discover");
  await rival.getByRole("region", { name: "Results" }).getByRole("button", { name: /Example Housing Trust Limited/ }).click();
  const theirs = rival.getByRole("complementary", { name: "Selected opportunity" });
  await expect(theirs.getByRole("region", { name: "Next move" })).toContainText("Research: Will the buyer extend");
  await expect(theirs.getByRole("region", { name: "Deal story" })).toContainText("Nothing recorded yet");
});
