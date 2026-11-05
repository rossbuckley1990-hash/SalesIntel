import { readFileSync } from "node:fs";
import { expect, test, type Browser, type Page } from "@playwright/test";

// The blind review, from both sides.
// - A reviewer judges an opportunity without knowing how it was found.
// - A salesperson outside the app does the same in an offline review pack, and their answers are imported.
// - The results stay sealed until the review is complete, locked and its key verified.
// - Live, paid research stays behind an approved budget.
const SHOTS = "../docs/saas/screenshots";

async function signUp(browser: Browser, email: string, name: string, company: string) {
  const page = await (await browser.newContext({ acceptDownloads: true })).newPage();
  await page.goto("/");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Company name").fill(company);
  await page.getByRole("button", { name: "Create workspace" }).click();
  return page;
}
const CHOICES: [string, string][] = [["genuine fire or security", "Yes"], ["correctly identified", "Yes"], ["requirement confirmed", "Hypothesised"],
  ["already been advertised", "Advertised"], ["legitimate reason", "Yes"], ["who to speak to", "A role only"], ["reliable business contact", "Unsure"],
  ["strong and current", "Adequate"], ["pursue it", "Yes, this month"]];
async function judge(page: Page) {
  const form = page.getByRole("form", { name: "Your judgement" });
  for (const [question, answer] of CHOICES) await form.getByRole("group", { name: new RegExp(question) }).getByText(answer, { exact: true }).click();
  return form;
}

test("a reviewer judges an opportunity blind, an offline pack comes back verified, and results stay sealed", async ({ browser }, info) => {
  const page = await signUp(browser, "rae.review@epsilon-quality.example", "Rae Review", "Epsilon Fire Ltd");
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor();
  await page.goto("/?view=review");
  const item = page.getByRole("article", { name: /^Item E-\d{2}$/ });
  await expect(item).toContainText("Source method hidden");
  await expect(item.getByRole("region", { name: "Evidence" })).toBeVisible();
  expect(await item.textContent()).not.toMatch(/radar|shadow|salesintel|window open|research says|engage now/i); // nothing about how it was found
  const form = page.getByRole("form", { name: "Your judgement" });
  await expect(form.getByRole("button", { name: /Save and next/ })).toBeDisabled(); // every question must be answered
  await judge(page);
  await form.getByLabel("Minutes spent").fill("4");
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/15-blind-review-desktop.png` });
  await form.getByRole("button", { name: /Save and next/ }).click();
  await expect(page.locator(".m-toast").filter({ hasText: /^Saved E-\d{2}\./ })).toBeVisible();
  await expect(page.getByText("judged by you")).toBeVisible();

  // The person running the evaluation: results are sealed, and locking needs two complete reviews of every item.
  const run = page.getByRole("region", { name: "Run the evaluation" });
  await expect(run.getByRole("region", { name: "Review results" })).toContainText("Results are sealed");
  await expect(run.getByRole("button", { name: "Lock the review" })).toBeDisabled();
  await expect(run.getByRole("region", { name: "Review progress" })).toContainText("1reviewer");

  // An offline pack for a salesperson: no network access, no key, and their own order of items.
  const [download] = await Promise.all([page.waitForEvent("download"), run.getByRole("button", { name: "Download pack" }).click()]);
  const packPath = info.outputPath("pack.html");
  await download.saveAs(packPath);
  const html = readFileSync(packPath, "utf8");
  expect(html).toContain("default-src 'none'");
  expect(html).not.toMatch(/sampled_by|in_pools|lead_key|qualified|exploratory/);
  const pack = await page.context().newPage();
  const requests: string[] = [];
  pack.on("request", (r) => { if (!r.url().startsWith("file:") && !r.url().startsWith("blob:")) requests.push(r.url()); });
  await pack.goto(`file://${packPath}`);
  await pack.getByLabel("Your name").fill("Dana Field");
  await pack.getByText("I will work alone").click();
  await pack.getByText("I will judge each item only on the evidence shown").click();
  await pack.getByRole("button", { name: "Start the review" }).click();
  for (let n = 0; n < 2; n++) {
    await expect(pack.getByRole("article", { name: /^Item E-\d{2}$/ })).toBeVisible();
    await judge(pack);
    if (n === 0) await pack.screenshot({ animations: "disabled", path: `${SHOTS}/18-offline-review-pack.png` });
    await pack.getByRole("form", { name: "Your judgement" }).getByRole("button", { name: /Save and (next|finish)/ }).click();
  }
  const [answers] = await Promise.all([pack.waitForEvent("download"), pack.getByRole("button", { name: "Download my answers" }).click()]);
  const answersPath = info.outputPath("answers.json");
  await answers.saveAs(answersPath);
  const sent = JSON.parse(readFileSync(answersPath, "utf8"));
  expect(sent.format).toBe("salesintel-review/1");
  expect(sent.decisions).toHaveLength(2);
  expect(requests).toEqual([]); // the pack sent nothing anywhere

  // Import: checked against the set's fingerprint and the rubric, then counted as a second, independent reviewer.
  await run.getByLabel("Import a reviewer's answers file").setInputFiles(answersPath);
  await expect(page.locator(".m-toast").filter({ hasText: /^Imported / })).toBeVisible();
  await expect(run.getByRole("region", { name: "Review progress" })).toContainText("2reviewers");
  await expect(run.getByRole("region", { name: "Review results" })).toContainText("Results are sealed");
  await run.scrollIntoViewIfNeeded();
  await run.screenshot({ animations: "disabled", path: `${SHOTS}/19-evaluation-control.png` });

  // The research budget: nothing approved, so live paid research is refused and nothing is charged.
  await page.getByRole("button", { name: "Team" }).click();
  const budget = page.getByRole("region", { name: "Research budget" });
  await expect(budget).toContainText("No budget approved");
  await expect(budget.getByRole("button", { name: "Approve" })).toBeVisible();
});
