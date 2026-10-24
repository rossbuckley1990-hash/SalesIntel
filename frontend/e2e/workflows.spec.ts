import { test, expect } from "@playwright/test";
import { resolve } from "node:path";
const api = "http://127.0.0.1:8011/api/living";
test("reviewed import is reversible and preserves unknown annual revenue", async ({
  page,
  request,
}) => {
  expect((await (await request.get(`${api}/workspace`)).json()).mode).toBe(
    "synthetic",
  );
  await page.goto("/?view=imports");
  await page.getByLabel("Choose tracker").setInputFiles({
    name: "reviewed-demo.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "Opportunity,Buyer,Revenue,Probability\nImport browser test,Fictional import buyer,240000,50%\n",
    ),
  });
  await page.getByRole("button", { name: "Preview and validate" }).click();
  await expect(
    page.getByRole("button", { name: "Commit reviewed import" }),
  ).toBeEnabled();
  await expect(page.locator("main")).toContainText("Fictional import buyer");
  await page.getByRole("button", { name: "Commit reviewed import" }).click();
  await expect(page.getByRole("status")).toContainText("import");
  const ws = await (await request.get(`${api}/workspace`)).json();
  const imported = ws.opportunities.find(
    (o: any) => o.name === "Import browser test",
  );
  expect(imported.financials.estimated_annual_revenue).toBeNull();
  await page
    .getByRole("button", {
      name: /Undo latest change: Commit reviewed tracker import/,
    })
    .click();
  await expect(page.getByRole("status")).toContainText(/has been undone/i);
  expect(
    (await (await request.get(`${api}/workspace`)).json()).opportunities.some(
      (o: any) => o.name === "Import browser test",
    ),
  ).toBe(false);
});
test("live scenario morphology reuses one renderer and exports reproducible Excel", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/?view=finance&opportunity=1");
  await page.getByRole("button", { name: "Explore in 3D" }).click();
  await page.waitForFunction(
    () => window.__MISI_FIELD_DIAGNOSTICS__?.activeEngines === 1,
  );
  const original = await page.locator("canvas").elementHandle();
  await page.getByLabel("Proposed self-delivery", { exact: true }).fill("85");
  await expect(page.locator(".m-scenario-hero")).toContainText("£61,380");
  expect(
    await original!.evaluate((el) => el === document.querySelector("canvas")),
  ).toBe(true);
  await expect(
    page.getByRole("button", { name: "Save scenario", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("Scenario name").fill("Excel reconciliation scenario");
  await page
    .getByRole("button", { name: "Save scenario", exact: true })
    .click();
  await page.getByRole("button", { name: "Build business case" }).click();
  await page
    .getByRole("button", { name: /Open asset/ })
    .first()
    .click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Excel workbook" }).click();
  await (await download).saveAs(resolve("../.runtime/scenario.xlsx"));
  expect(errors).toEqual([]);
});
test("tender exact-line extraction and source-bound capture", async ({
  page,
  request,
}) => {
  await page.goto("/?view=opportunities");
  await page
    .getByRole("button", { name: /Alderwick University/ })
    .first()
    .click();
  await page.getByRole("tab", { name: "Tender", exact: true }).click();
  await page
    .getByLabel("Requirement extract")
    .fill(
      "Context only.\nSupplier must provide the engineer competence records.\nThe contractor shall maintain a monthly inspection log.",
    );
  await page
    .getByLabel("Source reference")
    .fill("Synthetic specification page 7");
  await page
    .getByRole("button", { name: "Extract requirements from pasted source" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review extracted requirements" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save reviewed extracts" }).click();
  await expect(page.getByRole("status")).toContainText("saved");
  const detail = await (await request.get(`${api}/opportunities/1`)).json();
  expect(
    detail.requirements.some(
      (r: any) =>
        r.source_reference.includes("page 7") &&
        r.requirement.includes("competence records"),
    ),
  ).toBe(true);
});
test("API outage provides retry; classic core remains reachable", async ({
  page,
}) => {
  await page.route("**/api/living/workspace", (r) =>
    r.abort("connectionrefused"),
  );
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
  await page.unroute("**/api/living/workspace");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(
    page.getByRole("heading", { name: "Make your next move count." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Classic workspace" }).click();
  await expect(
    page.getByRole("link", { name: "← Living workspace" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Pipeline Forecast", exact: true })
    .first()
    .click();
  await expect(page.locator("body")).toContainText("April to March FY");
  await page
    .getByRole("button", { name: "Buyers", exact: true })
    .first()
    .click();
  await expect(page.locator("body")).toContainText("Alderwick");
});

test("explicit reduced-motion 3D renders on interaction and then sleeps", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?view=field&opportunity=1");
  await expect(
    page.getByRole("heading", { name: "Connected records" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Engineering capacity/ }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.getByRole("button", { name: "Spatial", exact: true }).click();
  await page.waitForFunction(
    () => window.__MISI_FIELD_DIAGNOSTICS__?.activeEngines === 1,
  );
  await page.waitForTimeout(1000);
  const before = await page.evaluate(
    () => window.__MISI_FIELD_DIAGNOSTICS__!.frames,
  );
  await page.waitForTimeout(300);
  expect(
    await page.evaluate(() => window.__MISI_FIELD_DIAGNOSTICS__!.frames),
  ).toBe(before);
  await page.locator("canvas").focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() => page.evaluate(() => window.__MISI_FIELD_DIAGNOSTICS__!.frames))
    .toBeGreaterThan(before);
});

test("selected opportunity follows the user from field to finance and actions", async ({
  page,
}) => {
  await page.goto("/?view=field&opportunity=1&webgl=off");
  await page.getByRole("combobox", { name: "Field focus" }).selectOption("3");
  await expect(page).toHaveURL(/opportunity=3/);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Finance", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "Opportunity", exact: true }),
  ).toHaveValue("3");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: /My Work/ })
    .click();
  await page.getByRole("button", { name: "Create action" }).click();
  await expect(
    page.getByRole("combobox", { name: "Linked opportunity" }),
  ).toHaveValue("3");
});
