import { expect, test, type Browser } from "@playwright/test";

// The interface layer: the command menu, keyboard jumps, and the phone sheet staying on screen.
async function signUp(browser: Browser, email: string, name: string, company: string, viewport?: { width: number; height: number }) {
  const page = await (await browser.newContext(viewport ? { viewport, isMobile: true, hasTouch: true } : {})).newPage();
  await page.goto("/");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Company name").fill(company);
  await page.getByRole("button", { name: "Create workspace" }).click();
  return page;
}

test("the command menu and keyboard jumps reach every workspace", async ({ browser }) => {
  const page = await signUp(browser, "kim.keys@delta-ui.example", "Kim Keys", "Delta Fire Ltd");
  await expect(page.getByRole("heading", { name: /Good (morning|afternoon|evening), Kim\./ })).toBeVisible();

  // Ctrl+K opens the menu; a typed place jumps there with the right source chosen.
  await page.keyboard.press("Control+k");
  const menu = page.getByRole("dialog", { name: "Command menu" });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("combobox", { name: "Search SalesIntel" })).toBeFocused();
  await page.keyboard.type("shadow");
  await expect(menu.getByRole("option").first()).toContainText("Shadow Radar");
  await page.keyboard.press("Enter");
  await expect(menu).toHaveCount(0);
  await expect(page).toHaveURL(/view=find&source=shadow/);
  await expect(page.getByRole("button", { name: /^Shadow Radar/ })).toHaveAttribute("aria-pressed", "true");

  // Free text becomes a Discover search; Escape closes without moving.
  await page.keyboard.press("Control+k");
  await expect(menu.getByRole("combobox", { name: "Search SalesIntel" })).toBeFocused();
  await page.keyboard.type("care homes in Yorkshire");
  await menu.getByRole("option", { name: /Search opportunities for/ }).click();
  await expect(page).toHaveURL(/view=find&q=care\+homes\+in\+Yorkshire/);
  await expect(page.getByLabel("Search opportunities")).toHaveValue("care homes in Yorkshire");
  await page.keyboard.press("Control+k");
  await expect(menu.getByRole("combobox", { name: "Search SalesIntel" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);

  // G then a letter jumps between workspaces, and the current one is marked for assistive technology.
  await page.locator("body").click({ position: { x: 600, y: 20 } });
  await page.keyboard.press("g");
  await page.keyboard.press("a");
  await expect(page).toHaveURL(/view=clients/);
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Accounts", exact: true })).toHaveAttribute("aria-current", "page");
  await page.keyboard.press("g");
  await page.keyboard.press("t");
  await expect(page).toHaveURL(/view=today/);
});

test("on a phone the opportunity sheet sits on screen and closes from outside", async ({ browser }) => {
  const page = await signUp(browser, "pat.phone@delta-ui.example", "Pat Phone", "Delta Fire Ltd", { width: 390, height: 844 });
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Discover", exact: true }).click();
  await page.getByRole("button", { name: /^Shadow Radar/ }).click();
  await page.getByRole("region", { name: "Results" }).getByRole("button", { name: /Harbourside Community Health/ }).first().click();
  const sheet = page.getByRole("region", { name: "Selected opportunity details" });
  await expect(sheet.getByRole("button", { name: "Investigate" })).toBeVisible();
  await sheet.evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished))); // measure where it comes to rest
  const box = await sheet.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y).toBeGreaterThan(0);
  expect(box!.y + box!.height).toBeLessThanOrEqual(844 + 1); // anchored to the screen, not the page
  await page.getByRole("button", { name: "Close details" }).click({ position: { x: 20, y: 80 } });
  await expect(sheet).toHaveCount(0);
});

test("the pipeline board moves a deal by dragging, keeps it after a reload, and undoes a move the server refuses", async ({ browser }) => {
  const page = await signUp(browser, "dana.drag@delta-ui.example", "Dana Drag", "Delta Fire Ltd");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  // A clearly fictional deal, created through the same API the interface uses.
  await page.evaluate(async () => {
    const headers = { Authorization: `Bearer ${sessionStorage.getItem("salesintel.session")}`, "X-SalesIntel-Workspace": sessionStorage.getItem("salesintel.workspace") || "", "Content-Type": "application/json" };
    const base = "http://127.0.0.1:8012/api/si";
    const account = await (await fetch(`${base}/accounts`, { method: "POST", headers, body: JSON.stringify({ name: "Example Dragline Estates" }) })).json();
    await fetch(`${base}/accounts/${account.account_id}/deals`, { method: "POST", headers, body: JSON.stringify({ title: "Fire alarm servicing, 4 sites", services: ["fire_alarm"], qualification: { requirement: "Annual servicing at four sites" }, value_total: 48000 }) });
  });
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Deals", exact: true }).click();
  const board = page.getByRole("list", { name: "Pipeline by stage" });
  const column = (stage: string) => board.getByRole("listitem", { name: stage, exact: true });
  const card = page.locator(".si-deal").filter({ hasText: "Fire alarm servicing, 4 sites" });
  await expect(column("Qualify")).toContainText("Fire alarm servicing, 4 sites");
  await expect(column("Qualify")).toContainText("£48,000");

  await card.dragTo(column("Engage"));
  await expect(page.locator(".m-toast").filter({ hasText: "moved to Engage" })).toBeVisible();
  await expect(column("Engage")).toContainText("Fire alarm servicing, 4 sites");
  await page.reload();
  await expect(column("Engage")).toContainText("Fire alarm servicing, 4 sites");

  // Approval needs a quotation: the server refuses, and the card goes back where it was.
  await card.getByLabel("Move Fire alarm servicing, 4 sites to").selectOption("approval");
  await expect(page.locator(".m-toast").filter({ hasText: "Build a quotation draft before commercial approval." })).toBeVisible();
  await expect(column("Engage")).toContainText("Fire alarm servicing, 4 sites");
  await expect(column("Approval")).not.toContainText("Fire alarm servicing, 4 sites");
});
