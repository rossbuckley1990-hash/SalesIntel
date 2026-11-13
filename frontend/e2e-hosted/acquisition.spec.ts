import { expect, test, type Browser, type Page } from "@playwright/test";

// Phase 2B acceptance: the acquisition engine through the real browser, API, database and research
// worker. Hosted mode with signed development tokens. Research is replayed offline from clearly
// synthetic pages that include adversarial content (a prompt-injection page, an invented address,
// a personal email). Screenshots are written to docs/saas/screenshots.
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

async function nav(page: Page, name: string, mobile = false) {
  if (mobile) await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name, exact: true }).click();
}

async function setUp(page: Page, { territory, sectors }: { territory: string; sectors: string }) {
  await page.getByRole("button", { name: "Set up" }).click();
  await page.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await page.getByRole("button", { name: "CCTV", exact: true }).click();
  await page.getByLabel("Territory").fill(territory);
  await page.getByLabel("Customer sectors").fill(sectors);
  await page.getByLabel("Smallest contract").fill("20000");
  await page.getByLabel("Largest contract").fill("750000");
  await page.getByLabel("Capabilities").fill("BAFE SP203-1, 24/7 call-out");
  await page.getByLabel("Target amount").fill("600,000");
  await page.getByLabel("Target measured as").selectOption("total_contract_value");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await toast(page, "Saved.");
}

test("public tender: notice, account, official procurement route, grounded introduction, follow-up, deal", async ({ browser }) => {
  const page = await signUp(browser, "alice.public@alpha-acquisition.example", "Alice Seller", "Alpha Fire Ltd");
  await setUp(page, { territory: "England", sectors: "Housing" });

  // Discover: the six questions, with the published notice and what is still unknown.
  await nav(page, "Discover");
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Example Housing Trust Limited/ }).click();
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByRole("heading", { name: /^Contract with Sample Fire Services Ltd ends/ })).toBeVisible();
  await expect(detail.getByRole("region", { name: "Next move" })).toBeVisible();
  await detail.getByText("Source record").click(); // the six questions, as first found, one click away
  for (const q of ["Why this customer?", "Why now?", "What do we know?", "What remains unknown?", "Who should we contact?", "What should we do next?"])
    await expect(detail.getByRole("region", { name: q })).toBeVisible();
  await expect(detail.getByText("Existing contract approaching a reported end date")).toBeVisible();
  await expect(detail.getByText(/a contract ending is not a confirmed tender/)).toBeVisible();
  await expect(detail.getByRole("region", { name: "Why this customer?" })).toContainText("In your territory: England");
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/1-discover-brief-desktop.png`, fullPage: false });

  // Save it as an account from the Action Dock, then find the people. The research is durable: refresh while it runs.
  await detail.getByRole("region", { name: "Next move" }).getByRole("button", { name: "Save as an account" }).click();
  await toast(page, /as an account/);
  await detail.getByRole("button", { name: /Open the full account/ }).click();
  await expect(page).toHaveURL(/view=clients&account=\d+/);
  const people = page.getByRole("region", { name: "Find the right people" });
  await people.getByRole("button", { name: "Find the right people" }).click();
  await page.reload();
  await expect(people.getByText(/Complete/)).toBeVisible({ timeout: 30000 });
  await expect(people.getByText(/Official procurement contact found/)).toBeVisible();
  const routes = people.getByRole("list", { name: "Best contact routes" });
  const official = routes.getByRole("listitem").filter({ hasText: "procurement@example-housing.example" });
  await expect(official).toContainText("Publicly sourced business contact");
  await expect(official).toContainText("Use only for questions about it, through the route the notice specifies");
  await expect(routes.getByRole("listitem").filter({ hasText: "Robin Sample" })).toContainText("Robin Sample, Head of Assets at Example Housing Trust");
  await expect(routes.getByRole("listitem").first()).toContainText("Best");
  await expect(page.getByText(/@gmail\.com/)).toHaveCount(0);
  await expect(people.getByText(/\$0\.19 \(simulated\)/)).toBeVisible();
  await people.screenshot({ animations: "disabled", path: `${SHOTS}/2-people-public-desktop.png` });

  // Prepare a grounded first approach to the official route; it is never sent by SalesIntel.
  await official.getByRole("button", { name: "Prepare introduction" }).click();
  await expect(page).toHaveURL(/view=engage/);
  const message = page.getByLabel("Message", { exact: true });
  await expect(message).toHaveValue(/Dear \[name\],|Dear Procurement/);
  await page.getByLabel("Your name").fill("Alice Seller");
  await page.getByLabel("Your company").fill("Alpha Fire Ltd");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Rebuild from evidence" }).click();
  await expect(message).toHaveValue(/Alice Seller/);
  await message.fill((await message.inputValue()).replace("Dear [name],", "Dear Procurement Team,"));
  await page.getByRole("button", { name: "Approve" }).click();
  await toast(page, /Approved/);
  await page.getByLabel("I sent this message myself").check();
  await page.getByRole("button", { name: "Log as sent" }).click();
  await toast(page, /Logged as sent/);
  await nav(page, "Today");
  await expect(page.getByText(/Follow up on introduction to Example Housing Trust Limited/).first()).toBeVisible();

  // Record the engagement and qualify the opportunity into the pipeline.
  await nav(page, "Accounts");
  await page.getByRole("button", { name: "Example Housing Trust Limited" }).click();
  await page.getByLabel("What happened").fill("Procurement team confirmed the re-tender is planned for spring");
  await page.getByLabel("Outcome").selectOption("requirement_captured");
  await page.getByRole("button", { name: "Save to timeline" }).click();
  await toast(page, /Logged/);
  await page.getByRole("button", { name: "Qualify into a deal" }).click();
  await page.getByLabel("Customer requirement (confirmed)").fill("Fire alarm servicing across 14 sheltered schemes, re-tender in spring");
  await page.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await page.getByRole("button", { name: "Create deal" }).click();
  await expect(page).toHaveURL(/view=deals&deal=\d+/);
  await expect(page.getByText("Insufficient historical data for a reliable win probability.")).toBeVisible();
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/3-deal-desktop.png` });
});

test("private prospect on a phone: brief, durable research, people, partial result, follow-up; another company sees none of it", async ({ browser }) => {
  const mobile = { width: 390, height: 844 };
  const page = await signUp(browser, "bdm@beta-acquisition.example", "Bea Developer", "Beta Security Ltd", mobile);
  await setUp(page, { territory: "Yorkshire", sectors: "Logistics" });

  // Specify a territory and sector, and research the web. The job survives a refresh.
  await nav(page, "Discover", true);
  await page.getByLabel("Search opportunities").fill("logistics companies with new warehouses in Yorkshire");
  await page.getByRole("button", { name: "Research the web" }).click();
  await toast(page, /keeps running if you leave or refresh/);
  await page.reload();
  await expect(page.getByText(/Web research: “logistics companies with new warehouses in Yorkshire”/)).toBeVisible();
  await expect(page.getByText(/2 organisation\(s\) found, each with its sources/)).toBeVisible({ timeout: 30000 });
  await page.reload();
  const results = page.getByRole("region", { name: "Results" });
  await results.getByRole("button", { name: /Northgate Distribution Ltd/ }).click();
  const sheet = page.getByRole("region", { name: "Selected opportunity details" });
  await expect(sheet.getByRole("region", { name: "Next move" })).toBeVisible();
  await sheet.getByText("Source record").click();
  await expect(sheet.getByText("Private organisation with an observable signal")).toBeVisible();
  await expect(sheet.getByRole("region", { name: "Why now?" })).toContainText("Announced a 400,000 sq ft distribution centre in Wakefield");
  await expect(sheet.getByRole("region", { name: "Why now?" })).toContainText("Inferred timing:");
  // Dates are written for people: the stored 2026-09-14 and the month 2027-06 are never shown as machine dates.
  await expect(sheet.getByRole("region", { name: "What do we know?" })).toContainText("14 September 2026");
  await expect(sheet.getByRole("region", { name: "What do we know?" })).toContainText("June 2027");
  await expect(sheet.getByRole("region", { name: "What do we know?" }).getByText(/\d{4}-\d\d/)).toHaveCount(0);
  await expect(sheet.getByRole("region", { name: "What remains unknown?" })).toContainText("not proof of buying intent");
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/4-discover-private-mobile.png` });
  await expect(results.getByRole("button", { name: /Calder Freight Services/ })).toContainText("Unverified");

  // Find the people: a named lead and permitted routes, but no direct details, said plainly.
  await sheet.getByRole("button", { name: "Save as an account" }).click();
  await toast(page, /as an account/);
  await sheet.getByRole("button", { name: /Open the full account/ }).click();
  const people = page.getByRole("region", { name: "Find the right people" });
  await people.getByRole("button", { name: "Find the right people" }).click();
  await expect(people.getByText("Relevant decision-maker role identified, but no verified direct business contact details found.")).toBeVisible({ timeout: 30000 });
  const routes = people.getByRole("list", { name: "Best contact routes" });
  await expect(routes.getByRole("listitem").filter({ hasText: "Sam Patel" })).toContainText("Head of Property");
  await expect(routes.getByRole("listitem").filter({ hasText: "0113 496 0000" })).toBeVisible();
  for (const fabricated of ["sam.patel@northgate-distribution.example", "md.northgate@gmail.com", "Alex Northgate"]) await expect(page.getByText(fabricated)).toHaveCount(0);
  await people.getByText(/finding\(s\) rejected/).click();
  await expect(people.getByText(/tried to give instructions to the AI/).first()).toBeVisible();
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/5-people-private-mobile.png`, fullPage: true });

  // Record the call to the switchboard and schedule the follow-up.
  await page.getByLabel("What happened").fill("Called the switchboard; asked for Sam Patel about the Wakefield site");
  await page.getByLabel("Outcome").selectOption("call_back");
  await page.getByRole("button", { name: "Save to timeline" }).click();
  await toast(page, /Logged/);
  await page.reload();
  await expect(page.getByText("Called the switchboard; asked for Sam Patel about the Wakefield site", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Deal story" })).toContainText("Call: Called the switchboard"); // the story keeps it too
  const accountUrl = page.url();

  // Another company cannot see the research, the account or the contacts.
  const rival = await signUp(browser, "rival@gamma-acquisition.example", "Rory Rival", "Gamma Fire Ltd");
  await rival.goto(accountUrl.replace(/^https?:\/\/[^/]+/, ""));
  await expect(rival.getByRole("alert").filter({ hasText: "Account not found" })).toBeVisible();
  await nav(rival, "Discover");
  await expect(rival.getByRole("region", { name: "Results" }).getByRole("button", { name: /Northgate Distribution Ltd/ })).toHaveCount(0);
  await expect(rival.getByText("Sam Patel")).toHaveCount(0);
});
