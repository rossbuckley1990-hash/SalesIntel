import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

// The research chat, through the real browser, API, database and research worker, in hosted mode. Research is
// replayed offline from fictional pages, including one that tries to instruct the model and a personal email.
const SHOTS = "../docs/saas/screenshots";

async function signUp(browser: Browser, email: string, name: string, company: string, viewport?: { width: number; height: number }) {
  const page = await (await browser.newContext(viewport ? { viewport, isMobile: true, hasTouch: true } : {})).newPage();
  await page.goto("/");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Company name").fill(company);
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  return page;
}

const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text }).first()).toBeVisible();

test("a rep asks in their own words; the reply researches, checks and offers a card they can save", async ({ browser }) => {
  const page = await signUp(browser, "rep@delta-chat.example", "Dee Rep", "Delta Fire Ltd");
  await page.goto("/?view=find");
  await page.getByRole("group", { name: "Discover mode" }).getByRole("button", { name: "Research chat" }).click();
  const chat = page.getByRole("region", { name: "Research chat" });
  await expect(chat.getByRole("heading", { name: "Find opportunities nobody has announced" })).toBeVisible();

  await chat.getByLabel("Message").fill("Logistics firms opening new warehouses in Yorkshire that nobody is tendering yet");
  await chat.getByLabel("Message").press("Enter");
  const log = chat.getByRole("list", { name: "Conversation" });
  await expect(log.getByText("Logistics firms opening new warehouses in Yorkshire that nobody is tendering yet")).toBeVisible();

  // The reply: what it did, what it found with numbered sources, and one checked card.
  await expect(log).toContainText("I found one organisation worth a call now", { timeout: 30000 });
  await expect(log.getByText(/What it did: 1 search, 1 page read, 5 checks/)).toBeVisible();
  await expect(log.getByRole("link", { name: "Source 1: Northgate Distribution plans Wakefield hub" }).first()).toBeVisible();
  const card = log.getByRole("article", { name: "Northgate Distribution Ltd" });
  await expect(card).toContainText("Hidden · 2 independent sources");
  await expect(card.getByRole("region", { name: "Dated facts" })).toContainText("14 September 2026");
  await expect(card.getByRole("region", { name: "Dated facts" })).toContainText("June 2027 (expected)");
  await expect(card).toContainText("Engage now");
  await expect(card).toContainText("By SalesIntel’s timing rules; a phase, not a forecast.");
  await expect(card).toContainText("No tender or early notice for it in SalesIntel’s public records.");
  await expect(card.getByRole("region", { name: "Who to approach" })).toContainText("Sam Patel, Head of Property");
  await expect(card.getByRole("region", { name: "Who to approach" })).toContainText("0113 496 0000");
  await expect(log.getByRole("article", { name: "Calder Freight Services" })).toHaveCount(0);  // no dated fact a page states
  await expect(page.getByText("md.northgate@gmail.com")).toHaveCount(0);  // planted by a page that tried to instruct the model
  await expect(log).toContainText(/This reply cost \$0\.\d\d/);
  await expect(log.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0);  // no probabilities
  await page.setViewportSize({ width: 1440, height: 1500 });  // the reply and its card above the message box
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/43-research-chat-desktop.png` });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const scan = await new AxeBuilder({ page }).include('[aria-label="Research chat"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);

  // Save it to Discover; a follow-up builds on what was found, and its sources keep their numbers.
  await card.getByRole("button", { name: "Save to Discover" }).click();
  await toast(page, "Northgate Distribution Ltd saved to Discover.");
  await expect(card.getByText("Saved to Discover")).toBeVisible();
  await chat.getByLabel("Message").fill("Who should I approach at Northgate?");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(log).toContainText("so he is the person to approach first", { timeout: 30000 });
  await expect(log.getByRole("link", { name: /^Source 2: / })).toHaveCount(2);
  await page.reload();  // the conversation is kept
  await expect(log).toContainText("so he is the person to approach first");
  const chatUrl = page.url();

  // A phone: the conversation fits.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(log.getByRole("article", { name: "Northgate Distribution Ltd" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await log.getByRole("article", { name: "Northgate Distribution Ltd" }).scrollIntoViewIfNeeded();
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/44-research-chat-mobile.png` });
  await page.setViewportSize({ width: 1440, height: 1000 });

  // Saved, it is a private lead in Discover.
  await log.getByRole("article", { name: "Northgate Distribution Ltd" }).getByRole("button", { name: /Open in Discover/ }).click();
  await expect(page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Northgate Distribution Ltd/ })).toBeVisible();

  // Another company cannot open the conversation.
  const rival = await signUp(browser, "rival@epsilon-chat.example", "Eve Rival", "Epsilon Security Ltd");
  await rival.goto(chatUrl.replace(/^https?:\/\/[^/]+/, ""));
  await expect(rival.locator(".m-toast").filter({ hasText: "That research chat no longer exists." })).toBeVisible();
  await expect(rival.getByText("Who should I approach at Northgate?")).toHaveCount(0);
});
