import { expect, test, type Browser } from "@playwright/test";

// PR #9: the blind review a salesperson uses to judge discovered opportunities, and the research budget that keeps live,
// paid research behind an explicit approval.
const SHOTS = "../docs/saas/screenshots";

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

test("a reviewer judges an opportunity without knowing its source, and only an administrator unblinds the results", async ({ browser }) => {
  const page = await signUp(browser, "rae.review@epsilon-quality.example", "Rae Review", "Epsilon Fire Ltd");
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor();
  await page.goto("/?view=review");
  const item = page.getByRole("article", { name: /^Item R-\d{3}$/ });
  await expect(item).toContainText("Source method hidden");
  await expect(item.getByRole("region", { name: "Evidence" })).toBeVisible();
  const form = page.getByRole("form", { name: "Your judgement" });
  await expect(form.getByRole("button", { name: /Save and next/ })).toBeDisabled(); // every question must be answered
  const choices: [string, string][] = [["genuine fire or security", "Yes"], ["correctly identified", "Yes"], ["requirement confirmed", "Hypothesised"],
    ["already been advertised", "Advertised"], ["legitimate reason", "Yes"], ["who to speak to", "A role only"], ["reliable business contact", "Unsure"],
    ["strong and current", "Adequate"], ["pursue it", "Yes, this month"]];
  for (const [question, answer] of choices) await form.getByRole("group", { name: new RegExp(question) }).getByText(answer, { exact: true }).click();
  await form.getByLabel("Minutes spent").fill("4");
  await page.screenshot({ animations: "disabled", path: `${SHOTS}/15-blind-review-desktop.png` });
  await form.getByRole("button", { name: /Save and next/ }).click();
  await expect(page.locator(".m-toast").filter({ hasText: /^Saved R-\d{3}\./ })).toBeVisible();
  await expect(page.getByText("judged by you")).toBeVisible();
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "See results (unblinds the methods)" }).click();
  const results = page.getByRole("region", { name: "Review results" });
  await expect(results).toContainText(/1 of \d+ items judged by 1 reviewer \(not complete\)/);
  await expect(results).toContainText("needs two reviewers per item");

  // The research budget: nothing approved, so live paid research is refused and nothing is charged.
  await page.getByRole("button", { name: "Team" }).click();
  const budget = page.getByRole("region", { name: "Research budget" });
  await expect(budget).toContainText("No budget approved");
  await expect(budget.getByRole("button", { name: "Approve" })).toBeVisible();
});
