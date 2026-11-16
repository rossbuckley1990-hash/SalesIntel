import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Defects from the sales field test of 16 November 2026, on fictional records: an internal note never makes an account
// "engaged", and a draft's warnings follow the recipient chosen. Uses an account of its own, so no other test can have moved it on.
const API = "http://127.0.0.1:8011/api/si";
const toast = (page: Page, text: RegExp | string) => expect(page.locator(".m-toast").filter({ hasText: text }).first()).toBeVisible();
const shot = (page: Page, name: string) => page.screenshot({ animations: "disabled", path: `../docs/saas/screenshots/${name}`, mask: [page.locator(".m-workspace-name")], maskColor: "#e4e7ec" });

test("a note keeps an account a prospect, and a draft's warnings follow the recipient", async ({ page }) => {
  const NAME = "Example Field Test Housing";
  const { account_id: id } = await (await page.request.post(`${API}/accounts`, { data: { name: NAME, sector: "Housing", region: "England" } })).json();
  await page.request.post(`${API}/accounts/${id}/activities`, { data: { kind: "note", direction: "internal", summary: "Desk research only. Nobody has been contacted yet." } });

  // Preparation is not engagement.
  await page.goto(`/?view=clients&account=${id}`);
  await expect(page.getByRole("heading", { name: NAME, level: 1 })).toBeVisible();
  const header = page.locator("main header").first();
  await expect(header).toContainText("prospect");
  await expect(header).not.toContainText("engaged");
  await shot(page, "37-note-keeps-prospect-desktop.png");

  // A real call that reached someone does change it.
  await page.request.post(`${API}/accounts/${id}/activities`, { data: { kind: "call", direction: "outbound", summary: "Spoke to the facilities team.", outcome: "connected" } });
  await page.reload();
  await expect(page.locator("main header").first()).toContainText("engaged");

  // A draft saved with no recipient (the introduction is prepared as the page opens); then a named person is chosen.
  await page.goto(`/?view=engage&account=${id}`);
  const warnings = page.getByText("Check before sending").locator("..");
  await expect(warnings).toContainText("No contact selected");
  await page.getByRole("button", { name: "Save draft" }).click();
  await toast(page, "Draft saved.");
  await page.request.post(`${API}/accounts/${id}/contacts`, { data: { name: "Example Person", role: "Head of Facilities" } });
  const drafts = await (await page.request.get(`${API}/drafts`)).json();
  const draft = drafts.items.find((x: { account_id: number }) => x.account_id === id);
  await page.goto(`/?view=engage&account=${id}&draft=${draft.id}`);
  await expect(warnings).toContainText("No contact selected");
  await page.getByRole("combobox", { name: "To", exact: true }).selectOption({ label: "Example Person" });
  await page.getByRole("button", { name: "Save draft" }).click();
  await toast(page, "Draft saved.");
  await expect(warnings).not.toContainText("No contact selected");
  await expect(warnings).toContainText("Example Person is selected, but no direct route to them is verified");
  await shot(page, "38-draft-warning-follows-recipient-desktop.png");
  const scan = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?view=clients&account=${id}`);
  await expect(page.getByRole("heading", { name: NAME, level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await shot(page, "39-account-status-mobile.png");
});
