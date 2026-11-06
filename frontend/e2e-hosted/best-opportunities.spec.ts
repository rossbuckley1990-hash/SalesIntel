import { writeFileSync } from "node:fs";
import { expect, test, type Browser, type Page } from "@playwright/test";

// Scenario A through the real browser, API, database and research worker (hosted mode, replayed research, no credit):
// an unadvertised opportunity found from indirect evidence, from the daily list to a qualified deal, with the time and
// the clicks each step of the salesperson's morning takes.
const SHOTS = "../docs/saas/screenshots";

async function signUp(browser: Browser, email: string, name: string, company: string, viewport?: { width: number; height: number }) {
  const page = await (await browser.newContext(viewport ? { viewport, isMobile: true, hasTouch: true } : {})).newPage();
  await page.goto("/");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Company name").fill(company);
  await page.getByRole("button", { name: "Create workspace" }).click();
  return page;
}
async function profile(page: Page) {
  await page.getByRole("button", { name: "Set up" }).click();
  await page.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await page.getByRole("button", { name: "Access control", exact: true }).click();
  await page.getByLabel("Territory").fill("England");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator(".m-toast").filter({ hasText: "Saved." })).toBeVisible();
}
const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text })).toBeVisible();

test("Scenario A: from the daily list to a qualified deal, with every claim sourced and every gap honest", async ({ browser }) => {
  const page = await signUp(browser, "sam.scout@delta-best.example", "Sam Scout", "Delta Fire Ltd");
  await profile(page);
  const marks: { step: string; seconds: number; clicks: number }[] = [];
  let clicks = 0;
  let t0 = Date.now();
  const mark = (step: string) => marks.push({ step, seconds: Math.round((Date.now() - t0) / 100) / 10, clicks });

  // 1. Understand why a lead matters: it is waiting when the day starts, with its reasons. Indirect evidence states no
  // requirement, so it is offered as worth investigating, labelled as unconfirmed, never as a confirmed need.
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Today", exact: true }).click(); clicks++;
  t0 = Date.now(); clicks = 0;
  const best = page.getByRole("region", { name: "Your best opportunities" });
  const card = best.getByRole("region", { name: "Worth investigating" }).getByRole("article", { name: /Harbourside Community Health/ });
  await expect(card).toContainText("Corroborated by 2 independent sources");
  await expect(card).toContainText("Inferred, not advertised");
  await expect(card).toContainText("Need not confirmed");
  await expect(best).not.toContainText(/\d+(\.\d+)?\s?%/); // no score or probability anywhere on the list
  mark("Understand why the lead matters");
  await card.getByText("The evidence, and what to confirm").click(); clicks++;
  await expect(card).toContainText("Estates, property or facilities manager");
  // Real organisations on SalesIntel's lists are masked in published screenshots, so none can tell a blind reviewer how an item was found.
  const real = best.getByRole("article").filter({ hasNotText: /Harbourside|Example Housing Trust|Sample Borough Council/ });
  await best.screenshot({ animations: "disabled", mask: [real], maskColor: "#efeee9", path: `${SHOTS}/10-best-opportunities-desktop.png` });

  // 2. Start an investigation, and 3. review its critical findings (including the evidence against it).
  await card.getByRole("button", { name: "Investigate Harbourside Community Health" }).click(); clicks++;
  await expect(page).toHaveURL(/view=clients&account=\d+/);
  const play = page.getByRole("region", { name: "Play" });
  await expect(play).toContainText("Play · New site");
  mark("Start an investigation");
  const investigation = page.getByRole("region", { name: "Investigation" });
  await expect(investigation.getByText("Evidence against it")).toBeVisible({ timeout: 30000 });
  await expect(investigation).toContainText("Coastline Fire Services");
  mark("Review the critical findings");

  // 4. A usable business contact route, with its confidence stated.
  const committee = page.getByRole("region", { name: "Buying committee" });
  const estates = committee.getByRole("listitem").filter({ hasText: "Estates or property director" });
  await expect(estates).toContainText("Morgan Reid");
  await expect(estates).toContainText("Publicly sourced");
  mark("Identify a usable contact route");

  // Missing information becomes research, and "not found" stays not found.
  const gaps = page.getByRole("region", { name: "Missing information" });
  await gaps.getByRole("button", { name: "Resolve this gap: Current fire and security supplier" }).click(); clicks++;
  const supplier = gaps.getByRole("listitem").filter({ hasText: "Current fire and security supplier" });
  await expect(supplier).toContainText("Resolved with evidence", { timeout: 20000 });
  await expect(supplier).toContainText("Coastline Fire Services");
  await expect(supplier).toContainText("Official source");
  await expect(supplier).toContainText("1 claim rejected: The page tried to give instructions to the AI");
  await gaps.getByRole("button", { name: "Resolve this gap: Who will run the site" }).click(); clicks++;
  const operator = gaps.getByRole("listitem").filter({ hasText: "Who will run the site" });
  await expect(operator).toContainText("Not found", { timeout: 20000 });
  await expect(operator).toContainText("nothing was guessed");
  await play.scrollIntoViewIfNeeded();
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/11-account-play-desktop.png`, fullPage: true });

  // 5. Prepare first contact from the evidence.
  await page.getByRole("button", { name: "Prepare introduction" }).first().click(); clicks++;
  await expect(page).toHaveURL(/view=engage/);
  await expect(page.getByLabel("Message", { exact: true })).toHaveValue(/Harbourside/, { timeout: 15000 });
  mark("Prepare first contact");
  await page.goBack(); clicks++;

  // 6. Set the next commercial action: log the call and its follow-up in one step.
  await page.getByLabel("What happened").fill("Called the estates team about the new diagnostic centre");
  await page.getByLabel("Outcome").selectOption("requirement_captured");
  await page.getByLabel("Requirement heard").fill("Fire alarm and access control for the new centre, via the main contractor package");
  await page.getByRole("button", { name: "Save to timeline" }).click(); clicks++;
  await toast(page, /Logged/);
  await expect(play.getByRole("button", { name: /Qualify into a deal/ })).toBeVisible(); // the play moved on by itself
  mark("Set the next commercial action");

  // Qualify, keeping the evidence, then see what discovery led to.
  await play.getByRole("button", { name: /Qualify into a deal/ }).click(); clicks++;
  await page.getByLabel("Customer requirement (confirmed)").fill("Fire alarm and access control package for the new diagnostic centre");
  await page.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await page.getByRole("button", { name: "Create deal" }).click();
  await expect(page).toHaveURL(/view=deals&deal=\d+/);
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Deals", exact: true }).click();
  await page.getByRole("button", { name: "Results from discovery" }).click();
  const results = page.getByRole("region", { name: "Results" });
  await expect(results).toContainText("Shadow Radar");
  await expect(results.getByRole("row").filter({ hasText: "Qualified into a deal" })).toContainText("1");
  await expect(results).toContainText("does not prove");
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/13-results-desktop.png` });

  // 7. Return the next morning: everything is still there, and the follow-up is on Today.
  await page.goto("/?view=today");
  t0 = Date.now(); clicks = 0;
  await expect(page.getByText(/Follow up with Harbourside Community Health|Called the estates team/).first()).toBeVisible();
  mark("Return and continue");
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Accounts", exact: true }).click();
  await page.getByRole("table").getByRole("button", { name: "Harbourside Community Health" }).click();
  await expect(page.getByRole("region", { name: "Missing information" }).getByRole("listitem").filter({ hasText: "Current fire and security supplier" })).toContainText("Coastline Fire Services");
  await expect(page.getByRole("region", { name: "Play" })).toContainText("Deal:");
  writeFileSync("../docs/saas/ux-timings.json", JSON.stringify({ scenario: "A: unadvertised new site, replayed research", recorded: new Date().toISOString().slice(0, 10), marks }, null, 2));
});

test("the best opportunities list reads well on a phone", async ({ browser }) => {
  const page = await signUp(browser, "pia.phone@delta-best.example", "Pia Phone", "Delta Fire Ltd", { width: 390, height: 844 });
  const best = page.getByRole("region", { name: "Your best opportunities" });
  await expect(best.getByRole("article").first()).toBeVisible();
  await best.scrollIntoViewIfNeeded();
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/14-best-opportunities-mobile.png` });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  // The account it opens, with its play, missing information and committee, also fits the screen.
  await best.getByRole("article").first().getByRole("button", { name: /^(Investigate|Open) / }).click();
  await expect(page).toHaveURL(/view=clients&account=\d+/);
  await expect(page.getByRole("region", { name: "Play" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Missing information" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth), "account page width").toBeLessThanOrEqual(390);
});
