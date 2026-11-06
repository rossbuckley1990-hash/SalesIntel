import { expect, test, type Browser, type Page } from "@playwright/test";

// Phase 2 acceptance through the browser, on the real API in hosted mode with signed development
// tokens and an isolated synthetic database. Two companies, one invited reviewer, no paid calls.

async function toast(page: Page, text: RegExp | string) {
  await expect(page.locator(".m-toast").filter({ hasText: text })).toBeVisible();
}
const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name, exact: true }).click();

async function signUp(browser: Browser, email: string, name: string, company?: string, path = "/") {
  const page = await (await browser.newContext()).newPage();
  await page.goto(path);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  if (company) {
    await page.getByLabel("Company name").fill(company);
    await page.getByRole("button", { name: "Create workspace" }).click();
  }
  return page;
}

test("a salesperson signs up, sets a target and takes a public lead to a qualified deal; another company sees none of it", async ({ browser }) => {
  const alice = await signUp(browser, "alice@alpha.example", "Alice Seller", "Alpha Fire Ltd");
  await expect(alice.getByText("Tell SalesIntel what you sell, where, and your target.")).toBeVisible();
  await alice.getByRole("button", { name: "Set up" }).click();
  await alice.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await alice.getByLabel("Territory").fill("England");
  await alice.getByLabel("Target amount").fill("500,000");
  await alice.getByLabel("Target measured as").selectOption("total_contract_value");
  await alice.getByRole("button", { name: "Save", exact: true }).click();
  await toast(alice, "Saved.");
  await expect(alice.getByText("Tell SalesIntel what you sell")).toHaveCount(0);

  // Discover a sourced public lead and prepare a grounded first approach. Nothing is sent.
  await nav(alice, "Discover");
  await alice.getByRole("region", { name: "Results" }).getByRole("button", { name: /Example Housing Trust Limited/ }).click();
  const detail = alice.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByRole("heading", { name: /^Contract with Sample Fire Services Ltd ends/ })).toBeVisible();
  await detail.getByRole("region", { name: "Next move" }).getByRole("button", { name: /Prepare introduction/ }).click();
  const message = alice.getByLabel("Message", { exact: true });
  await expect(message).toHaveValue(/Dear \[name\],/);
  await alice.getByLabel("Your name").fill("Alice Seller");
  await alice.getByLabel("Your company").fill("Alpha Fire Ltd");
  await alice.getByRole("button", { name: "Save", exact: true }).click();
  await alice.getByRole("button", { name: "Rebuild from evidence" }).click();
  await expect(message).toHaveValue(/Alice Seller/);
  await message.fill((await message.inputValue()).replace("Dear [name],", "Dear Assets team,"));
  await alice.getByRole("button", { name: "Approve" }).click();
  await toast(alice, /Approved/);
  await alice.getByLabel("I sent this message myself").check();
  await alice.getByRole("button", { name: "Log as sent" }).click();
  await toast(alice, /Logged as sent/);
  await nav(alice, "Today");
  await expect(alice.getByText(/Follow up on introduction to Example Housing Trust Limited/).first()).toBeVisible();

  // Log the conversation and qualify it into the pipeline.
  await nav(alice, "Accounts");
  await alice.getByRole("button", { name: "Example Housing Trust Limited" }).click();
  await alice.getByLabel("What happened").fill("Called the assets team about the sheltered schemes");
  await alice.getByLabel("Outcome").selectOption("requirement_captured");
  await alice.getByRole("button", { name: "Save to timeline" }).click();
  await toast(alice, /Logged/);
  await alice.getByRole("button", { name: "Qualify into a deal" }).click();
  await alice.getByLabel("Customer requirement (confirmed)").fill("Annual fire alarm servicing at 14 schemes");
  await alice.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await alice.getByRole("button", { name: "Create deal" }).click();
  await expect(alice).toHaveURL(/view=deals&deal=\d+/);
  const dealUrl = alice.url();

  // Can we win this? Fit and readiness now; no invented percentage.
  const assessment = alice.getByRole("region", { name: "Win probability" });
  await expect(assessment.getByText("Insufficient historical data for a reliable win probability.")).toBeVisible();
  const fit = alice.locator("section[aria-label='Commercial fit']");
  await expect(fit.getByText("Services we deliver")).toBeVisible();
  await expect(fit.locator("li").filter({ hasText: "Services we deliver" })).toContainText("Met");
  await expect(fit.locator("li").filter({ hasText: "Required accreditations held" })).toContainText("Unknown");
  await expect(alice.locator("section[aria-label='Win readiness']").locator("li").filter({ hasText: "Decision-maker identified" })).toContainText("Find out who signs off");
  await alice.getByLabel("Your confidence").selectOption("medium");
  await alice.reload();
  await expect(alice.getByLabel("Your confidence")).toHaveValue("medium");
  await expect(alice.getByText("Called the assets team about the sheltered schemes")).toBeVisible();

  // Another company: the same public notice is available to it, but nothing Alpha did is visible.
  const bob = await signUp(browser, "bob@beta.example", "Bob Rival", "Beta Security Ltd");
  await nav(bob, "Accounts");
  await expect(bob.getByText("No accounts yet")).toBeVisible();
  await nav(bob, "Discover");
  await bob.getByRole("region", { name: "Results" }).getByRole("button", { name: /Example Housing Trust Limited/ }).click();
  await expect(bob.getByRole("complementary", { name: "Selected opportunity" }).getByRole("region", { name: "Next move" })).toBeVisible();
  await expect(bob.getByRole("complementary", { name: "Selected opportunity" }).getByText("Same name (unconfirmed)")).toHaveCount(0); // none of Alpha's account
  await expect(bob.getByRole("complementary", { name: "Selected opportunity" }).getByRole("region", { name: "Deal story" })).toContainText("Nothing recorded yet");
  await bob.goto(dealUrl);
  await toast(bob, "Deal not found");
  await expect(bob.getByText("Annual fire alarm servicing at 14 schemes")).toHaveCount(0);
});

test("an administrator invites a read-only reviewer, whose changes the server refuses", async ({ browser }) => {
  const admin = await signUp(browser, "ann@gamma.example", "Ann Admin", "Gamma Fire Ltd");
  await admin.getByRole("button", { name: "Team" }).click();
  await admin.getByLabel("Colleague's email").fill("rita@gamma.example");
  await admin.getByLabel("Their role").selectOption("reviewer");
  await admin.getByRole("button", { name: "Create invitation" }).click();
  const link = await admin.getByLabel("Invitation link").inputValue();
  expect(link).toMatch(/\?invite=/);

  const rita = await signUp(browser, "rita@gamma.example", "Rita Review", undefined, link.replace(/^https?:\/\/[^/]+/, ""));
  await expect(rita.getByText("Gamma Fire Ltd").first()).toBeVisible();
  await expect(rita.getByText("Read-only reviewer")).toBeVisible();
  await nav(rita, "Accounts");
  await rita.getByRole("button", { name: "New account" }).click();
  await rita.getByLabel("Organisation name").fill("Should Not Exist Ltd");
  await rita.getByRole("button", { name: "Create", exact: true }).click();
  await toast(rita, "Your role does not allow this.");
  await admin.reload();
  await expect(admin.getByLabel("Role for Rita Review")).toHaveValue("reviewer");

  // The invitation was single-use: someone else with the link gets nothing.
  const eve = await signUp(browser, "eve@evil.example", "Eve", undefined, link.replace(/^https?:\/\/[^/]+/, ""));
  await expect(eve.getByRole("alert").filter({ hasText: "This invitation is not valid for your account." })).toBeVisible();
  await expect(eve.getByText("Create your company workspace")).toBeVisible();
  await expect(eve.getByText("Gamma Fire Ltd")).toHaveCount(0);
});
