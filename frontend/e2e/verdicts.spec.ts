import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// A rep's one-tap verdict on a lead, on fictional records. Three verdicts; each is stored with the evidence shown; "Wrong" hides
// the lead and tapping it again brings it back; Today counts what was said. Nothing here changes the order of a list.
const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text }).first()).toBeVisible();
// The single-user shell names the employer's workspace; it never appears in published screenshots.
const shot = (page: Page, name: string) => page.screenshot({ animations: "disabled", path: `../docs/saas/screenshots/${name}`, mask: [page.locator(".m-workspace-name")], maskColor: "#e4e7ec" });

test("a lead takes a one-tap verdict, Today counts it, and Wrong hides the lead until it is taken back", async ({ page }) => {
  await page.goto("/?view=find");
  const results = page.getByRole("region", { name: "Results" });
  const order = async () => results.getByRole("button").evaluateAll((rows) => rows.map((r) => r.getAttribute("aria-labelledby") || ""));
  await expect(results.getByRole("button", { name: /Ashby Vale Council/ })).toBeVisible();
  const before = await order();
  await results.getByRole("button", { name: /Ashby Vale Council/ }).click();
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  const verdict = detail.getByRole("region", { name: "Your verdict" });
  await expect(verdict.getByRole("button")).toHaveCount(3);
  for (const label of ["Didn’t know, worth a call", "Knew already", "Wrong"]) await expect(verdict.getByRole("button", { name: label })).toHaveAttribute("aria-pressed", "false");

  // One tap, and it survives a reload.
  await verdict.getByRole("button", { name: "Didn’t know, worth a call" }).click();
  await toast(page, "Verdict recorded.");
  await expect(verdict.getByRole("button", { name: "Didn’t know, worth a call" })).toHaveAttribute("aria-pressed", "true");
  expect(await order()).toEqual(before); // praise moves nothing
  await page.reload();
  await results.getByRole("button", { name: /Ashby Vale Council/ }).click();
  await expect(verdict.getByRole("button", { name: "Didn’t know, worth a call" })).toHaveAttribute("aria-pressed", "true");
  await verdict.scrollIntoViewIfNeeded();
  await shot(page, "31-verdict-brief-desktop.png");
  const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);

  // "Wrong" hides the lead from the list; tapping it again brings it back, in its old place.
  await results.getByRole("button", { name: /Fenwick Housing Trust/ }).click();
  await verdict.getByRole("button", { name: "Wrong" }).click();
  await toast(page, "Marked wrong. It is hidden from your lists.");
  await expect(results.getByRole("button", { name: /Fenwick Housing Trust/ })).toHaveCount(0);

  // Today counts what was said, as counts.
  await page.goto("/?view=today");
  const said = page.getByRole("region", { name: "Verdicts", exact: true });
  await expect(said).toContainText("1 of 2 judged leads: didn’t know, worth a call");
  await expect(said).toContainText("0 knew already · 1 wrong");
  await expect(said.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0);
  await said.scrollIntoViewIfNeeded();
  await shot(page, "32-verdict-today-desktop.png");

  // Taken back from the lead itself, opened by its key.
  await page.goto("/?view=find&status=dismissed");
  await page.getByLabel("Status").selectOption("dismissed");
  await results.getByRole("button", { name: /Fenwick Housing Trust/ }).click();
  await expect(verdict.getByRole("button", { name: "Wrong" })).toHaveAttribute("aria-pressed", "true");
  await verdict.getByRole("button", { name: "Wrong" }).click();
  await toast(page, "Verdict taken back.");
  await page.goto("/?view=find");
  await expect(results.getByRole("button", { name: /Fenwick Housing Trust/ })).toBeVisible();
  expect(await order()).toEqual(before);

  // A phone: the verdict follows what was read, fits, and is accessible.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=find");
  await results.getByRole("button", { name: /Ashby Vale Council/ }).click();
  const sheet = page.getByRole("region", { name: "Selected opportunity details" });
  const mobile = sheet.getByRole("region", { name: "Your verdict" });
  await expect(mobile.getByRole("button", { name: "Didn’t know, worth a call" })).toHaveAttribute("aria-pressed", "true");
  await mobile.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  const phone = await new AxeBuilder({ page }).include(".si-sheet").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(phone.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await shot(page, "33-verdict-brief-mobile.png");

  // Left as found, so later specs see the same list: the verdict on the tender is taken back too.
  await mobile.getByRole("button", { name: "Didn’t know, worth a call" }).click();
  await toast(page, "Verdict taken back.");
});
