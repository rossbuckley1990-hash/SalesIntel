import { expect, test, type Browser, type Page } from "@playwright/test";

// Shadow Radar acceptance through the real browser, API, database and research worker (hosted mode).
// The radar runs on a real capture of published Contracts Finder notices (5 November 2026) plus one
// clearly synthetic organisation, Harbourside Community Health, whose deep research is replayed offline.
const SHOTS = "../docs/saas/screenshots";

async function toast(page: Page, text: RegExp | string) {
  await expect(page.locator(".m-toast").filter({ hasText: text })).toBeVisible();
}
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
const nav = async (page: Page, name: string, mobile = false) => {
  if (mobile) await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name, exact: true }).click();
};

test("an unadvertised opportunity: evidence, investigation that challenges itself, contact, outreach and a deal that keeps the research", async ({ browser }) => {
  const page = await signUp(browser, "sam.shadow@alpha-radar.example", "Sam Seller", "Alpha Fire Ltd");
  await nav(page, "Discover");
  await page.getByRole("button", { name: /^Shadow Radar/ }).click();
  const results = page.getByRole("region", { name: "Results" });
  await results.getByRole("button", { name: /Harbourside Community Health/ }).first().click();
  const card = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(card.getByText("Corroborated by independent sources", { exact: true })).toBeVisible();
  await expect(card.getByRole("region", { name: "Competing hypotheses" })).toContainText("New premises");
  await expect(card.getByText("Inferred, not advertised")).toBeVisible();
  await expect(card.getByText("2 independent sources")).toBeVisible();
  await expect(card.getByRole("region", { name: "Potential requirement" })).toContainText("Northbank Construction Ltd");
  const timeline = card.getByRole("region", { name: "Evidence timeline" });
  await expect(timeline).toContainText("granted planning permission");
  await expect(timeline).toContainText("awarded \"Harbourside Community Diagnostic Centre - Main Works\"");
  for (const region of ["What is verified", "What is inferred", "What is unknown", "Alternative explanations", "Best next action"]) await expect(card.getByRole("region", { name: region })).toBeVisible();
  await expect(card.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0); // no percentage is shown anywhere on the card
  await expect(card.getByText(/No probability is shown/)).toBeHidden(); // said plainly inside the collapsed "how this was inferred"
  await page.screenshot({ path: `${SHOTS}/6-shadow-card-desktop.png` });

  // Investigate: the research tries to disprove the hypothesis as well as confirm it.
  await card.getByRole("button", { name: "Investigate" }).click();
  await expect(page).toHaveURL(/view=clients&account=\d+/);
  const investigation = page.getByRole("region", { name: "Investigation" });
  await expect(investigation.getByText("Evidence against it")).toBeVisible({ timeout: 30000 });
  await expect(investigation.getByRole("list", { name: "Questions tested" })).toContainText("Against");
  await expect(investigation).toContainText("Coastline Fire Services");
  await expect(investigation).toContainText("tendered to our approved supply chain in early 2027");
  await expect(page.getByText(/£2m fire alarm contract/)).toHaveCount(0); // injected claim rejected
  await expect(page.getByText(/budgeted £400,000/)).toHaveCount(0); // unquotable claim rejected
  await investigation.getByText(/finding\(s\) rejected/).click();
  await expect(investigation.getByText(/tried to give instructions to the AI/)).toBeVisible();
  await investigation.screenshot({ path: `${SHOTS}/7-investigation-desktop.png` });

  // The people were found in the same investigation.
  const people = page.getByRole("region", { name: "Find the right people" });
  await expect(people.getByRole("listitem").filter({ hasText: "Morgan Reid" })).toContainText("Director of Estates and Facilities");
  const estates = people.getByRole("listitem").filter({ hasText: "estates@harbourside-health.example" });
  await estates.getByRole("button", { name: "Prepare introduction" }).click();
  await expect(page).toHaveURL(/view=engage/);
  const message = page.getByLabel("Message", { exact: true });
  await page.getByLabel("Your name").fill("Sam Seller");
  await page.getByLabel("Your company").fill("Alpha Fire Ltd");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Rebuild from evidence" }).click();
  await expect(message).toHaveValue(/Sam Seller/);
  await message.fill((await message.inputValue()).replace("Dear [name],", "Dear Estates team,"));
  await page.getByRole("button", { name: "Approve" }).click();
  await toast(page, /Approved/);
  await page.getByLabel("I sent this message myself").check();
  await page.getByRole("button", { name: "Log as sent" }).click();
  await toast(page, /Logged as sent/);

  // Qualify: the deal keeps the original evidence and the investigation.
  await nav(page, "Accounts");
  await page.getByRole("button", { name: "Harbourside Community Health" }).click();
  await page.getByRole("button", { name: "Qualify into a deal" }).click();
  await page.getByLabel("Customer requirement (confirmed)").fill("Fire and security package for the new diagnostic centre, via the main contractor");
  await page.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await page.getByRole("button", { name: "Create deal" }).click();
  await expect(page).toHaveURL(/view=deals&deal=\d+/);
  await expect(page.getByLabel("Investigation carried into this deal")).toContainText("evidence was found against the original hypothesis");
  await expect(page.getByText("Insufficient historical data for a reliable win probability.")).toBeVisible();

  // A real captured lead: recorded as not relevant, with a reason, and hidden for this workspace.
  await nav(page, "Discover");
  await page.getByRole("button", { name: /^Shadow Radar/ }).click();
  await results.getByRole("button", { name: /Anchor Housing/ }).first().click();
  await expect(card.getByText(/purchasing consortium/)).toBeVisible(); // owner inferred from a consortium notice, said as such
  await expect(card.getByRole("region", { name: "Evidence timeline" })).toContainText("Meldrum Group Limited");
  await page.screenshot({ path: `${SHOTS}/8-shadow-real-lead-desktop.png` });
  await card.getByRole("button", { name: "Not relevant" }).click();
  await card.getByLabel("Reason").selectOption("outside_territory");
  await card.getByRole("button", { name: "Record and hide" }).click();
  await toast(page, /Recorded and hidden/);
  await expect(results.getByRole("button", { name: /Anchor Housing/ })).toHaveCount(0);

  // Another company: the shared public lead is there, Alpha's work is not.
  const rival = await signUp(browser, "rory.shadow@beta-radar.example", "Rory Rival", "Beta Security Ltd");
  await nav(rival, "Discover");
  await rival.getByRole("button", { name: /^Shadow Radar/ }).click();
  await expect(rival.getByRole("region", { name: "Results" }).getByRole("button", { name: /Anchor Housing/ }).first()).toBeVisible();
  await rival.getByRole("region", { name: "Results" }).getByRole("button", { name: /Harbourside Community Health/ }).first().click();
  await expect(rival.getByRole("region", { name: "Relationship history" })).toHaveCount(0);
  await nav(rival, "Accounts");
  await expect(rival.getByText("No accounts yet")).toBeVisible();
});

test("the Shadow Radar card works on a phone", async ({ browser }) => {
  const page = await signUp(browser, "mo.shadow@gamma-radar.example", "Mo Mobile", "Gamma Fire Ltd", { width: 390, height: 844 });
  await nav(page, "Discover", true);
  await page.getByRole("button", { name: /^Shadow Radar/ }).click();
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Harbourside Community Health/ }).first().click();
  const sheet = page.getByRole("region", { name: "Selected opportunity details" });
  await expect(sheet.getByText("Corroborated by independent sources", { exact: true })).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Investigate" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/9-shadow-card-mobile.png` });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
