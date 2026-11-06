import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser } from "@playwright/test";

// Contract Atlas, on an entirely fictional market (backend/app/services/atlas_fixtures.py): who holds the work, what
// public pages report about private customers (replayed research), and turning a competitor-held contract into an account.
const SHOTS = "../docs/saas/screenshots";

async function signUp(browser: Browser, email: string, name: string, company: string) {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Company name").fill(company);
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor();
  return page;
}

test("a salesperson sees who holds the work, what public pages report, and turns a contract into an account", async ({ browser }) => {
  const page = await signUp(browser, "ash.atlas@kappa-atlas.example", "Ash Atlas", "Kappa Fire Ltd");
  await page.goto("/?view=find&mode=atlas");
  await expect(page.getByRole("heading", { name: "Who holds the work" })).toBeVisible();
  await page.getByLabel("Contractor or customer").fill("Kestrel");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const contractors = page.getByRole("region", { name: "Contractors", exact: true });
  await contractors.getByRole("button", { name: /KESTREL FIRE SERVICES LTD/ }).click();
  const record = page.getByRole("article", { name: "Contractor KESTREL FIRE SERVICES LTD" });
  await expect(record).toContainText("Companies House 09876543");
  await expect(record).toContainText("Controlled by KESTREL FIRE HOLDINGS LTD"); // the group is shown; its contracts stay with each company
  await expect(record).toContainText("Framework appointment"); // not a contract to win, and its ceiling is not revenue
  await expect(record).toContainText("current status not established"); // a passed end date is never called ended

  // What public pages report about private customers: replayed research, checked against each page.
  const reported = record.getByRole("region", { name: "Reported customers" });
  await reported.getByRole("button", { name: "Research published customers" }).click();
  await expect(reported).toContainText("Northmoor Care Group", { timeout: 30000 });
  await expect(reported).toContainText("Quote found on the page");
  await expect(reported).toContainText("Subcontract via Castleford FM Services");
  await expect(reported).toContainText("Historical"); // a 2019 case study is a past job
  await expect(reported).toContainText("Quote not found word for word on the page"); // a paraphrase is flagged, not trusted
  await expect(reported).toContainText("2 claims were not supported"); // a customer the page never names, and a page never retrieved
  await expect(reported).not.toContainText("Fenwick Housing Trust");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/20-contract-atlas.png` });
  await record.screenshot({ animations: "disabled", path: `${SHOTS}/21-contract-atlas-contractor.png` });
  const scan = await new AxeBuilder({ page }).include("#atlas-record").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);

  // A researched private customer is findable, with its reported supplier.
  await page.getByLabel("Contractor or customer").fill("Northmoor");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("region", { name: "Customers", exact: true }).getByRole("button", { name: /Northmoor Care Group/ }).click();
  const customer = page.getByRole("article", { name: "Customer Northmoor Care Group" });
  await expect(customer).toContainText("Reported by a public source; current status not established: Kestrel Fire Services Ltd");

  // From a competitor-held contract to an account, linked to the contract and its evidence, without retyping anything.
  await page.getByLabel("Contractor or customer").fill("Kestrel Fire Services");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("region", { name: "Contractors", exact: true }).getByRole("button", { name: /KESTREL FIRE SERVICES LTD/ }).click();
  await page.getByRole("button", { name: "Investigate Fenwick Housing Trust" }).click();
  await expect(page).toHaveURL(/view=clients/);
  await expect(page.getByRole("heading", { name: "Fenwick Housing Trust" })).toBeVisible();
  const suppliers = page.getByRole("region", { name: "Who supplies them" });
  await expect(suppliers).toContainText("Published supplier in term: KESTREL FIRE SERVICES LTD");
  await suppliers.scrollIntoViewIfNeeded();
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/22-contract-atlas-account.png` });
});

test("researched relationships stay in the workspace that researched them", async ({ browser }) => {
  const page = await signUp(browser, "lee.other@lambda-atlas.example", "Lee Other", "Lambda Security Ltd");
  await page.goto("/?view=find&mode=atlas&q=Kestrel%20Fire%20Services");
  await page.getByRole("region", { name: "Contractors", exact: true }).getByRole("button", { name: /KESTREL FIRE SERVICES LTD/ }).click();
  const record = page.getByRole("article", { name: "Contractor KESTREL FIRE SERVICES LTD" });
  await expect(record).toContainText("Companies House 09876543"); // published contracts are shared public facts
  await expect(record.getByRole("region", { name: "Reported customers" })).toContainText("None recorded yet"); // another workspace's research is not
});
