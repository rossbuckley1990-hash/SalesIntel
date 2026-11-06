import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The Living Opportunity on fictional records (backend/app/services/living_fixtures.py): Fernhill Parcels' depot programme
// and Ashby Vale Council's live tender. Demo mode: web research is refused, so nothing is charged and the dock says why.
const SHOTS = "../docs/saas/screenshots";
const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text })).toBeVisible();
const marks: { step: string; seconds: number; clicks: number }[] = [];
// The single-user shell names the employer's workspace; it never appears in published screenshots.
const shot = (page: Page, name: string) => page.screenshot({ animations: "disabled", path: `${SHOTS}/${name}`, mask: [page.locator(".m-workspace-name")], maskColor: "#e4e7ec" });

test("a private signal: the reveal, the evidence, one next move, and the journey to a deal with continuity", async ({ page }) => {
  let clicks = 0;
  let t0 = Date.now();
  const mark = (step: string) => marks.push({ step, seconds: Math.round((Date.now() - t0) / 100) / 10, clicks });

  await page.goto("/?view=find");
  const results = page.getByRole("region", { name: "Results" });
  await expect(results.getByRole("button", { name: /Fernhill Parcels Ltd/ })).toBeVisible();
  t0 = Date.now();
  await results.getByRole("button", { name: /Fernhill Parcels Ltd/ }).click(); clicks++;
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });

  // The reveal: what happened, why it could matter, what could be sold, what could disprove it, what to find out next.
  await expect(detail.getByRole("heading", { name: "£240m programme for six new automated parcel depots" })).toBeVisible();
  mark("Reveal readable after choosing the lead");
  await expect(detail.getByRole("region", { name: "Why it could matter" })).toContainText("Bristol depot due to open");
  await expect(detail.getByRole("region", { name: "Why it could matter" })).not.toContainText("Wakefield"); // an opening already past is not a window
  await expect(detail.getByText("Rule of thumb, not a fact")).toBeVisible();
  await expect(detail.getByRole("list", { name: "Possible, not stated" })).toContainText("CCTV");
  await expect(detail.getByRole("list", { name: "Named in a source" })).toHaveCount(0); // no source names a system
  await expect(detail.getByRole("region", { name: "What could make it irrelevant" })).toContainText("Halden Construction appointed main contractor");
  await expect(detail.getByRole("region", { name: "What to find out next" })).toContainText("already been awarded");
  await expect(detail.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0); // no probability anywhere

  // The evidence timeline keeps its dates apart and says what each source does not establish.
  const river = detail.getByRole("region", { name: "Evidence, newest first" });
  await expect(river).toContainText("Expected");
  await expect(river).toContainText("Weakens");
  await river.getByRole("button", { name: /Halden Construction appointed main contractor/ }).click(); clicks++;
  await expect(river.getByText("What it does not establish")).toBeVisible();
  await expect(detail.getByRole("region", { name: "Who is involved" })).toContainText("Main contractor for the Bristol depot");

  // One next move, with why, what it produces, and the research that would come first but cannot run here.
  const dock = detail.getByRole("region", { name: "Next move" });
  await expect(dock).toContainText("Prepare introduction");
  await expect(dock).toContainText("Nothing is sent automatically");
  await expect(dock).toContainText("switched off in demo mode");
  await expect(detail.getByRole("region", { name: "Questions that decide this opportunity" }).getByRole("button", { name: /Research this/ })).toHaveCount(0); // never a dead button
  await river.getByRole("button", { name: /Halden Construction appointed main contractor/ }).click(); // fold the detail away again for the picture
  await detail.evaluate((el) => { el.scrollTop = 0; });
  await page.waitForTimeout(400);
  await shot(page, "23-living-discover-desktop.png");
  mark("Understood the lead and its next move");

  // Record the first conversation from the dock: it saves the account first, then keeps what the customer said.
  t0 = Date.now(); clicks = 0;
  await dock.getByRole("button", { name: /Log the first contact/ }).click(); clicks++;
  await toast(page, "Saved Fernhill Parcels Ltd as an account.");
  await dock.getByLabel("What happened").fill("Called Priya Shah about the Swindon depot");
  await dock.getByLabel("Outcome").selectOption("requirement_captured");
  await dock.getByRole("button", { name: "+ Requirements, objections, commitments" }).click(); clicks++;
  await dock.getByLabel("Requirement heard").fill("Fire alarm and CCTV design for the Swindon depot, tender in spring");
  await dock.getByRole("button", { name: "Save to timeline" }).click(); clicks++;
  await toast(page, /Logged/);

  // The customer stated a requirement, so the one next move is now to qualify it; the requirement is carried over.
  await expect(dock).toContainText("Qualify into a deal");
  await expect(detail.getByRole("region", { name: "Path to a deal" }).getByText("Establish the need and the buyer (done)")).toBeAttached();
  await dock.getByRole("button", { name: "Qualify into a deal" }).first().click(); clicks++;
  await expect(dock.getByLabel("Customer requirement (confirmed)")).toHaveValue("Fire alarm and CCTV design for the Swindon depot, tender in spring");
  await dock.getByRole("button", { name: "Fire alarm", exact: true }).click(); clicks++;
  await dock.getByRole("button", { name: "Create deal" }).click(); clicks++;
  await expect(page).toHaveURL(/view=deals&deal=\d+/);
  mark("From the lead to a qualified deal");

  // Continuity: the account opens on the same brief, and the story is built from what was recorded.
  await page.goto("/?view=clients");
  await page.getByRole("button", { name: "Fernhill Parcels Ltd" }).click();
  await page.reload();
  const story = page.getByRole("region", { name: "Deal story" });
  await expect(story).toContainText("Call: Called Priya Shah about the Swindon depot");
  await expect(story).toContainText("Requirement: Fire alarm and CCTV design");
  await expect(story).toContainText("Deal:");
  await expect(page.getByRole("region", { name: "Next move" }).first()).not.toContainText("Qualify into a deal");
  await expect(page.locator(".si-strip")).toHaveCount(0); // the empty 26-week graphic is gone
  await page.waitForTimeout(400);
  await shot(page, "24-living-account-desktop.png");
});

test("a published tender: named services, the eligibility question, and no rule of thumb", async ({ page }) => {
  await page.goto("/?view=find");
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Ashby Vale Council/ }).click();
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByRole("heading", { name: "Fire alarm and emergency lighting maintenance across council buildings" })).toBeVisible();
  await expect(detail.getByText(/Ashby Vale Council published this tender; responses are due \d{1,2} [A-Z][a-z]+ \d{4}/)).toBeVisible();
  await expect(detail.getByRole("list", { name: "Named in a source" })).toContainText("Emergency lighting");
  await expect(detail.getByRole("region", { name: "What to find out next" })).toContainText("mandatory requirements");
  await expect(detail.getByText("Rule of thumb, not a fact")).toHaveCount(0);
  await expect(detail.getByRole("region", { name: "Path to a deal" })).toContainText("Decide bid or no bid");
  // The record as first found is kept, one click away.
  await detail.getByText("Source record").click();
  await expect(detail.getByRole("region", { name: "Why this customer?" })).toBeVisible();
});

test("Today is a briefing, and the new screens are accessible and fit a phone", async ({ page }) => {
  await page.goto("/?view=today");
  const briefing = page.getByRole("group", { name: "Intelligence briefing" });
  for (const part of ["Discovered", "Changed", "Needs action", "Could move revenue", "Worth watching"]) await expect(briefing.getByRole("region", { name: part })).toBeVisible();
  await expect(page.getByText("Nothing is waiting on you")).toHaveCount(0);
  await page.waitForTimeout(400);
  await shot(page, "25-living-today-desktop.png");

  for (const url of ["/?view=today", "/?view=find", "/?view=clients&account=1"]) {
    await page.goto(url);
    await expect(page.locator("main h1").first()).toBeVisible();
    if (url.includes("find")) await expect(page.getByRole("region", { name: "Next move" }).first()).toBeVisible();
    const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(scan.violations.map((v) => ({ url, id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  }

  // Tablet: the brief and its dock, no sideways scrolling.
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.goto("/?view=find");
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Fernhill Parcels Ltd/ }).click();
  await expect(page.getByRole("region", { name: "Selected opportunity details" }).getByRole("region", { name: "Next move" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(820);

  // Keyboard: j and k move through the list and the brief follows; every dock action is a real, focusable button.
  await page.setViewportSize({ width: 1512, height: 1100 });
  await page.goto("/?view=find");
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByRole("heading", { level: 2 }).first()).toBeVisible();
  const first = await detail.getByRole("heading", { level: 2 }).first().innerText();
  await page.keyboard.press("j");
  await expect(detail.getByRole("heading", { level: 2 }).first()).not.toHaveText(first);
  const primary = detail.getByRole("region", { name: "Next move" }).getByRole("button").first();
  await primary.focus();
  await expect(primary).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=find");
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Fernhill Parcels Ltd/ }).click();
  const sheet = page.getByRole("region", { name: "Selected opportunity details" });
  await expect(sheet.getByRole("heading", { name: "£240m programme for six new automated parcel depots" })).toBeVisible();
  // On a phone, what happened is read before the next move.
  const order = await sheet.evaluate((el) => {
    const h = el.querySelector(".lo-headline")!, dock = el.querySelector('[aria-label="Next move"]')!;
    return h.compareDocumentPosition(dock) & Node.DOCUMENT_POSITION_FOLLOWING ? "reveal first" : "dock first";
  });
  expect(order).toBe("reveal first");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  const phone = await new AxeBuilder({ page }).include(".si-sheet").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(phone.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await shot(page, "26-living-discover-mobile.png");

  mkdirSync("../docs/saas/living", { recursive: true });
  writeFileSync("../docs/saas/living/ux-measurements.json", JSON.stringify({ suite: "local, demo mode, fictional fixtures", recorded: new Date().toISOString().slice(0, 10), marks }, null, 2));
});

test("reduced motion is honoured", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto("/?view=find");
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Fernhill Parcels Ltd/ }).click();
  const chevron = page.getByRole("complementary", { name: "Selected opportunity" }).locator(".lo-event-title svg").first();
  await expect(chevron).toBeVisible();
  expect(await chevron.evaluate((el) => getComputedStyle(el).transitionDuration)).toMatch(/^0s$|^1e-06s$|0\.001ms|1e-06/);
  await context.close();
});
