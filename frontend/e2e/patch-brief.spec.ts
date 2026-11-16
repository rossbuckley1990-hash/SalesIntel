import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The patch brief on fictional records: the first thing a rep sees, and the thing the owner sends. Five leads with no typing,
// each with a dated evidence chain labelled Published or Inferred, one next action and a one-tap verdict. A patch is set with
// taps; a judged lead leaves the five and "worth a call" stays in reach; the brief copies as text to send.
const API = "http://127.0.0.1:8011/api/si";
const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text }).first()).toBeVisible();
// The single-user shell names the employer's workspace; it never appears in published screenshots.
const shot = (page: Page, name: string) => page.screenshot({ animations: "disabled", path: `../docs/saas/screenshots/${name}`, mask: [page.locator(".m-workspace-name")], maskColor: "#e4e7ec" });

test("a rep sees five leads for their patch with no typing, judges them with a tap, and the brief is ready to send", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  // Start from no rep, whatever ran before.
  const start = await (await page.request.get(`${API}/patch/reps`)).json();
  for (const r of start.reps) await page.request.delete(`${API}/patch/reps/${encodeURIComponent(r.name)}`);

  // First value: five leads, inside ten seconds, with nothing typed. Timed on a warm page, as a rep meets it.
  await page.goto("/?view=today");
  const brief = page.getByRole("region", { name: "Patch brief" });
  await expect(brief.getByRole("article")).toHaveCount(5);
  const t0 = Date.now();
  await page.goto("/?view=today");
  await expect(brief.getByRole("article")).toHaveCount(5);
  expect(Date.now() - t0).toBeLessThan(10_000);
  await expect(brief.getByRole("heading", { name: "This week from the public record" })).toBeVisible();

  // Each lead: the organisation, why now, the chain (every published record opens its source), the next action, the verdict.
  const fenwick = brief.getByRole("article", { name: "Fenwick Housing Trust" });
  await expect(fenwick).toContainText("Two or more independent records");
  await expect(fenwick).toContainText("Why now: Early procurement notice");
  const chain = fenwick.getByRole("list", { name: "Evidence for Fenwick Housing Trust" }).getByRole("listitem");
  await expect(chain).toHaveCount(3);
  await expect(chain.nth(0)).toContainText("The Regulator of Social Housing graded Fenwick Housing Trust C3");
  await expect(chain.nth(0).getByRole("link")).toHaveAttribute("href", "https://regulator.example/judgements/fenwick-housing-trust");
  await expect(chain.nth(0)).toContainText("Published");
  await expect(chain.nth(1).getByRole("link")).toHaveAttribute("href", "https://procurement.example/notices/fenwick-early-engagement");
  await expect(chain.nth(2)).toContainText("Inferred");
  await expect(chain.nth(2).getByRole("link")).toHaveCount(0); // SalesIntel's reading is not a source
  await expect(fenwick.getByRole("button", { name: /^Next: Read the record at its source/ })).toBeVisible();
  await expect(fenwick.getByRole("group", { name: "Verdict on Fenwick Housing Trust" }).getByRole("button")).toHaveCount(3);
  await expect(brief.getByText(/\d{4}-\d\d-\d\d/)).toHaveCount(0); // no machine dates
  await expect(brief.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0); // no probability
  await shot(page, "34-patch-brief-desktop.png");
  const scan = await new AxeBuilder({ page }).include('[aria-label="Patch brief"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);

  // A phone: the same five, nothing scrolling sideways.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=today");
  await expect(brief.getByRole("article")).toHaveCount(5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  const phone = await new AxeBuilder({ page }).include('[aria-label="Patch brief"]').withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(phone.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await brief.scrollIntoViewIfNeeded();
  await shot(page, "35-patch-brief-mobile.png");
  await page.setViewportSize({ width: 1512, height: 1100 });

  // The patch is set with taps. Two quick taps both count.
  await brief.getByRole("button", { name: "Set up your patch" }).click();
  const form = brief.getByRole("form", { name: "Patch" });
  await expect(form.getByLabel("Whose patch is this?")).toHaveValue("My patch");
  await form.getByRole("button", { name: /^Yorkshire and the Humber/ }).click();
  await form.getByRole("button", { name: "Fire alarm", exact: true }).click();
  await shot(page, "36-patch-setup-desktop.png");
  await form.getByRole("button", { name: "Save and show the five" }).click();
  await toast(page, "Patch saved.");
  await expect(brief.getByRole("heading", { name: "Patch brief: My patch" })).toBeVisible();
  await expect(brief).toContainText("Yorkshire and the Humber");
  await expect(brief.getByRole("article")).toHaveCount(1); // the one lead whose own notice states this region
  const ashby = brief.getByRole("article", { name: "Ashby Vale Council" });
  await expect(ashby).toContainText("A published deadline still ahead");
  await expect(ashby.getByRole("list", { name: "Evidence for Ashby Vale Council" }).getByRole("listitem")).toHaveCount(2); // a tender needs no reading added

  // Ready to send: plain text, with the links and the reply letters. SalesIntel sends nothing.
  await brief.getByRole("button", { name: "Copy to send" }).click();
  await toast(page, "Copied. Paste it into an email: SalesIntel sends nothing.");
  const sent = await page.evaluate(() => navigator.clipboard.readText());
  expect(sent).toContain("SalesIntel patch brief for My patch");
  expect(sent).toContain("1. Ashby Vale Council  [Published tender]");
  expect(sent).toContain("[Published] https://www.contractsfinder.service.gov.uk/Notice/living-fixture-ashby");
  expect(sent).toContain("A = Didn’t know, worth a call   B = Knew already   C = Wrong");
  expect(sent).not.toMatch(/\d{4}-\d\d-\d\d/);

  // One tap: the lead leaves the five, stays in reach as worth a call, and is counted for this rep.
  await ashby.getByRole("button", { name: "Didn’t know, worth a call" }).click();
  await toast(page, "Verdict recorded. The next lead has moved up.");
  await expect(brief.getByRole("article")).toHaveCount(0);
  await expect(brief.getByRole("group", { name: "Worth a call" })).toContainText("Ashby Vale Council");
  await expect(brief).toContainText("1 of 1 judged lead: didn’t know, worth a call.");
  await expect(brief).toContainText("You have judged every lead held for this patch.");

  // The verdict was recorded against this rep, and a brief opened anywhere shows it.
  await brief.getByRole("group", { name: "Worth a call" }).getByRole("button", { name: /Ashby Vale Council/ }).click();
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByRole("region", { name: "Your verdict" }).getByRole("button", { name: "Didn’t know, worth a call" })).toHaveAttribute("aria-pressed", "true");
  const tally = await (await page.request.get(`${API}/brief/verdicts`, { params: { rep: "My patch" } })).json();
  expect(tally.headline).toBe("1 of 1 judged lead: didn’t know, worth a call");

  // Everything held in the patch, in Discover's own order.
  await page.goto("/?view=today");
  await brief.getByRole("button", { name: "Everything held in Yorkshire and the Humber" }).click();
  await expect(page).toHaveURL(/view=find/);
  const results = page.getByRole("region", { name: "Results" });
  await expect(results.getByRole("button")).toHaveCount(1);
  await expect(results.getByRole("button", { name: /Ashby Vale Council/ })).toBeVisible();
  await page.getByRole("button", { name: /Region: Yorkshire and the Humber/ }).click();
  await expect(results.getByRole("button", { name: /Fernhill Parcels Ltd/ })).toBeVisible();

  // Left as found, so later specs see the same lists: the verdict is taken back and the rep removed.
  await page.goto("/?view=today");
  await brief.getByText("Judged so far (1)").click();
  await brief.getByRole("button", { name: "Take back" }).click();
  await toast(page, "Verdict taken back.");
  await expect(brief.getByRole("article", { name: "Ashby Vale Council" })).toBeVisible();
  await page.request.delete(`${API}/patch/reps/${encodeURIComponent("My patch")}`);
  expect((await (await page.request.get(`${API}/brief/verdicts`)).json()).judged).toBe(0);
});
