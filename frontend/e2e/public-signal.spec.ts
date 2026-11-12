import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// A public record before any tender, on a fictional one (backend/app/services/living_fixtures.py): a regulator's finding about
// Fenwick Housing Trust and, later, the trust's own early notice. Two records from two independent sources. The trust is also a
// buyer in the fictional Contract Atlas, so the brief sets the signal beside the published holder without connecting the two.
const HEADLINE = 'Fenwick Housing Trust published an early notice: "Fire alarm replacement and remedial works programme"';

test("a public signal is found on Today and by kind, and is briefed as a record, never as a contract", async ({ page }) => {
  await page.goto("/?view=today");
  const briefing = page.getByRole("group", { name: "Intelligence briefing" });
  for (const part of ["Discovered", "Changed", "Needs action", "Could move revenue", "Worth watching"]) await expect(briefing.getByRole("region", { name: part })).toBeVisible();
  const signals = page.getByRole("region", { name: "Before any tender" });
  const row = signals.getByRole("button", { name: /Fenwick Housing Trust/ });
  await expect(row).toContainText(HEADLINE);
  await expect(row).toContainText("2 public records from 2 independent sources");
  await expect(signals).toContainText("None is a published requirement.");
  await expect(briefing).not.toContainText("Fenwick Housing Trust"); // an inference is never listed among the published leads
  await row.click();

  // The brief: what the newest record says, why it could matter and no further, and the questions that decide it.
  const detail = page.getByRole("complementary", { name: "Selected opportunity" });
  await expect(detail.getByRole("heading", { name: HEADLINE })).toBeVisible();
  await expect(detail.getByText("Not a requirement: verify")).toBeVisible();
  const why = detail.getByRole("region", { name: "Why it could matter" });
  await expect(why).toContainText("Neither record says the two are connected");
  await expect(why).toContainText("Do not repeat it to a customer as fact.");
  await expect(detail.getByText("Rule of thumb, not a fact")).toHaveCount(0); // no renewal pattern: it is not a contract
  await expect(detail.getByText(/\d+(\.\d+)?\s?%/)).toHaveCount(0); // no probability anywhere
  await expect(detail.getByText(/\d{4}-\d\d-\d\d/)).toHaveCount(0); // no machine dates
  const questions = detail.getByRole("region", { name: "Questions that decide this opportunity" });
  await expect(questions).toContainText("Is the problem in the record still open at Fenwick Housing Trust");
  await expect(questions).toContainText("When will the tender be published, and by which procedure or framework?");
  // A published holder is a lead on the answer, never the answer, and is never tied to the regulator's finding.
  const field = detail.getByRole("region", { name: "The competitive field" });
  await expect(field).toContainText("holds a published contract with this buyer for fire or security work");
  await expect(field).toContainText("It does not confirm who delivers the work today, or that this contract covers what the record describes.");
  await expect(detail.getByRole("region", { name: "Path to a deal" })).toContainText("Confirm the problem is still open");
  // The first move is to read the record itself.
  await expect(detail.getByRole("region", { name: "Next move" }).getByRole("button", { name: "Read the record at its source" }).first()).toBeVisible();
  const brief = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(brief.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);

  // Discover, by kind: the one signal, labelled as what it is.
  await page.goto("/?view=find");
  const results = page.getByRole("region", { name: "Results" });
  await expect(results.getByRole("button", { name: /Fernhill Parcels Ltd/ })).toBeVisible();
  await page.getByLabel("Kind").selectOption("inferred_signal");
  await expect(results.getByRole("button")).toHaveCount(1);
  await expect(results.getByRole("button", { name: /Fenwick Housing Trust/ })).toContainText("Public signal");
  await expect(results.getByRole("button", { name: /Fenwick Housing Trust/ })).toContainText("A reason to ask, not a published requirement.");
  await page.getByLabel("Kind").selectOption("live_procurement");
  await expect(results.getByRole("button", { name: /Ashby Vale Council/ })).toBeVisible();
  await expect(results.getByRole("button", { name: /Fenwick Housing Trust/ })).toHaveCount(0);

  // A phone: the Today list and the brief fit, with nothing scrolling sideways.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=today");
  await expect(page.getByRole("region", { name: "Before any tender" }).getByRole("button", { name: /Fenwick Housing Trust/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  const today = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(today.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await page.getByRole("region", { name: "Before any tender" }).getByRole("button", { name: /Fenwick Housing Trust/ }).click();
  await expect(page.getByRole("region", { name: "Selected opportunity details" }).getByRole("heading", { name: HEADLINE })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
