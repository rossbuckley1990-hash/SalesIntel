import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { resolve } from "node:path";
const api = "http://127.0.0.1:8011/api/living";
async function ready(page: Page, view = "today", suffix = "") {
  await page.goto(`/?view=${view}${suffix}`);
  await expect(page.locator("main h1")).toBeVisible();
}
async function openFirstAsset(page: Page) {
  await page
    .getByRole("button", { name: /Open asset/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
}
test.beforeEach(async ({ request }) => {
  const r = await request.get(`${api}/workspace`);
  expect((await r.json()).mode).toBe("synthetic");
});
test("A: question → evidence → decision → dossier → exported files → reopened record", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await ready(page, "discover");
  await page.getByText("Search internal records", { exact: true }).click();
  await page
    .getByLabel("Commercial question")
    .fill(
      "Find fire and security maintenance opportunities at universities in Yorkshire",
    );
  await page
    .getByRole("button", { name: "Explore intelligence", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /connected opportunit/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Assemble in the field" }).click();
  await expect(page.getByLabel("Field focus", { exact: true })).toBeVisible();
  await page.getByLabel("Field focus", { exact: true }).selectOption("1");
  await page.getByRole("button", { name: "Accessible data view" }).click();
  await page.getByRole("button", { name: "Open full workspace" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("tab", { name: /Evidence/ }).click();
  await expect(
    dialog.getByText("Engineering capacity", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("tab", { name: "Decision", exact: true }).click();
  await dialog
    .getByRole("combobox", { name: "Decision", exact: true })
    .selectOption("pursue");
  await dialog
    .getByLabel("Reviewer", { exact: true })
    .fill("Demo bid reviewer");
  await dialog
    .getByLabel("Decision rationale")
    .fill(
      "Synthetic source reviewed; pursuit is conditional on resolving engineering capacity.",
    );
  await dialog
    .getByLabel("Next action")
    .fill("Obtain the regional capacity assessment for the bid review");
  await dialog.getByLabel("Responsible owner").fill("Demo action owner");
  await dialog.getByLabel("Due date").fill("2026-11-02");
  await dialog
    .getByRole("button", { name: "Record decision and action" })
    .click();
  await expect(page.getByRole("status")).toContainText("Decision");
  await dialog.getByRole("button", { name: "Build pursuit pack" }).click();
  await expect(page.locator("main h1")).toHaveText(
    "Intelligence. Ready to use.",
  );
  await openFirstAsset(page);
  await expect(page.getByRole("dialog")).toContainText("engineering capacity");
  for (const [label, ext] of [
    ["Download PDF", "pdf"],
    ["Editable Word", "docx"],
    ["Excel workbook", "xlsx"],
  ]) {
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: label }).click();
    const file = await download;
    expect(await file.failure()).toBeNull();
    await file.saveAs(resolve(`../.runtime/dossier.${ext}`));
  }
  await page.reload();
  await openFirstAsset(page);
  await expect(page.getByRole("dialog")).toContainText("Demo action owner");
  const detail = await (await request.get(`${api}/opportunities/1`)).json();
  expect(detail.outcome.stage).toBe("approved");
  expect(errors).toEqual([]);
});
test("B: scenario changes calculate without persistence, explicit save creates editable business case", async ({
  page,
  request,
}) => {
  await ready(page, "selfDelivery", "&opportunity=1");
  const before = await (await request.get(`${api}/scenarios`)).json();
  await page.getByLabel("Annual revenue", { exact: true }).fill("1000000");
  await page.getByLabel("Probability of award", { exact: true }).fill("60");
  await expect(
    page.getByRole("button", { name: "Save scenario", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("Proposed self-delivery", { exact: true }).fill("70");
  await expect(
    page.getByText("£314,000 gross margin", { exact: true }),
  ).toBeVisible();
  expect((await (await request.get(`${api}/scenarios`)).json()).length).toBe(
    before.length,
  );
  await page
    .getByLabel("Scenario name")
    .fill("Verified demonstration 40 to 70");
  await page
    .getByRole("button", { name: "Save scenario", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Build business case" }),
  ).toBeEnabled();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    (document.activeElement as HTMLElement)?.blur();
  });
  await page.screenshot({
    path: resolve("../.runtime/scenario-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Build business case" }).click();
  await openFirstAsset(page);
  await expect(page.getByRole("dialog")).toContainText("£28,800");
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Editable Word" }).click();
  await (await download).saveAs(resolve("../.runtime/business-case.docx"));
});
test("C: Today exposes actual changes and produces a leadership briefing", async ({
  page,
}) => {
  await ready(page);
  await expect(
    page.getByRole("heading", { name: "What changed", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Accepted snapshots/)).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Tools", exact: true }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Asset Studio", exact: true })
    .click();
  await page.getByRole("button", { name: /Leadership briefing/ }).click();
  await page.getByRole("button", { name: "Build asset", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Executive financial position",
  );
  await expect(page.getByRole("dialog")).toContainText(/source register/i);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download PDF" }).click();
  await (await download).saveAs(resolve("../.runtime/leadership.pdf"));
});
test("D: reveal an at-risk deal and complete an owned pursuit action with evidence", async ({
  page,
  request,
}) => {
  await ready(page, "field", "&opportunity=3");
  await page.getByRole("button", { name: "Reveal risk" }).click();
  await page.getByRole("button", { name: "Accessible data view" }).click();
  await expect(
    page.getByText("Engineering capacity", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "My Work", exact: false })
    .first()
    .click();
  await page.getByRole("button", { name: "Create action" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Linked opportunity").selectOption("3");
  await dialog
    .getByLabel("Action", { exact: true })
    .fill("Validate the health estate mobilisation capacity");
  await dialog
    .getByLabel("Why now and commercial consequence")
    .fill(
      "Red recorded risk threatens the submission date and estimated margin.",
    );
  await dialog
    .getByLabel("Owner", { exact: true })
    .fill("Demo operations lead");
  await dialog.getByLabel("Due date").fill("2026-11-01");
  await dialog.getByRole("button", { name: "Save action" }).click();
  const row = page
    .locator("article")
    .filter({ hasText: "Validate the health estate mobilisation capacity" });
  await row.getByRole("button", { name: "Continue" }).click();
  await dialog
    .getByRole("combobox", { name: "Status", exact: true })
    .selectOption("completed");
  await dialog
    .getByLabel("Completion evidence")
    .fill("Synthetic capacity review CR-001 approved for demonstration only.");
  await dialog.getByRole("button", { name: "Save action" }).click();
  await expect(row).toContainText("Completed");
  const details = await (await request.get(`${api}/opportunities/3`)).json();
  expect(
    details.actions.find((a: any) => a.owner === "Demo operations lead")
      .completion_evidence,
  ).toContain("CR-001");
});
test("keyboard command, responsive layout, reduced motion, no-WebGL fallback and a11y", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await ready(page);
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Search and command" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  for (const view of [
    "today",
    "opportunities",
    "finance",
    "actions",
    "assets",
    "outcomes",
    "field",
  ]) {
    await ready(page, view, "&opportunity=1&webgl=off");
    const scan = await new AxeBuilder({ page })
      .include("main")
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      scan.violations.map((v) => ({
        id: v.id,
        targets: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
  }
  await expect(
    page.getByRole("heading", { name: "Connected records" }),
  ).toBeVisible();
  expect(await page.locator("canvas").count()).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  await page.screenshot({
    path: resolve("../.runtime/today-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
});
test("GPU lifecycle: repeated navigation, resize, live morph and context loss", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  await ready(page, "field", "&opportunity=1");
  const samples = [];
  for (let i = 0; i < 3; i++) {
    if (i)
      await page
        .getByRole("button", { name: "Intelligence Field", exact: false })
        .first()
        .click();
    await page.waitForFunction(
      () =>
        window.__MISI_FIELD_DIAGNOSTICS__?.activeEngines === 1 &&
        window.__MISI_FIELD_DIAGNOSTICS__.frames > 160,
    );
    await page.setViewportSize({ width: 1400 + i * 20, height: 1000 });
    await expect(page.locator("canvas")).toBeVisible();
    samples.push(
      await page.evaluate(() => ({ ...window.__MISI_FIELD_DIAGNOSTICS__ })),
    );
    if (i === 2)
      await page.screenshot({
        path: resolve("../.runtime/field-desktop.png"),
        fullPage: true,
      });
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await page.waitForFunction(
      () => window.__MISI_FIELD_DIAGNOSTICS__?.activeEngines === 0,
    );
    const frames = await page.evaluate(
      () => window.__MISI_FIELD_DIAGNOSTICS__!.frames,
    );
    await page.waitForTimeout(150);
    expect(
      await page.evaluate(() => window.__MISI_FIELD_DIAGNOSTICS__!.frames),
    ).toBe(frames);
  }
  expect(samples.every((s) => s.duplicateFrames === 0)).toBe(true);
  expect(
    Math.max(...samples.map((s) => s.textures || 0)) -
      Math.min(...samples.map((s) => s.textures || 0)),
  ).toBeLessThanOrEqual(2);
  await page
    .getByRole("button", { name: "Intelligence Field", exact: false })
    .first()
    .click();
  await page.waitForFunction(
    () => window.__MISI_FIELD_DIAGNOSTICS__?.activeEngines === 1,
  );
  await page
    .locator("canvas")
    .evaluate((c: HTMLCanvasElement) =>
      c.getContext("webgl2")?.getExtension("WEBGL_lose_context")?.loseContext(),
    );
  await expect(
    page.getByRole("heading", { name: "Connected records" }),
  ).toBeVisible();
  await page.waitForFunction(
    () => window.__MISI_FIELD_DIAGNOSTICS__?.activeEngines === 0,
  );
  expect(errors).toEqual([]);
  console.log("GPU samples", JSON.stringify(samples));
});
