import { test } from "@playwright/test";
import path from "node:path";

// Captures the real workspace with its configured data; never injects sample leads.
test("capture workspace for visual review", async ({ page }) => {
  const stage = process.env.MISI_VISUAL_STAGE || "after";
  const destination = path.resolve(process.cwd(), "../visual-review");
  for (const view of ["today", "discover"]) {
    for (const [label, width, height] of [["desktop", 1440, 1050], ["mobile", 390, 844]] as const) {
      await page.setViewportSize({ width, height });
      await page.goto(`/?view=${view}`, { waitUntil: "networkidle" });
      await page.screenshot({ path: path.join(destination, `${stage}-${view}-${label}.png`), fullPage: false, animations: "disabled" });
      if (view === "discover") {
        const leads = page.getByRole("region", { name: "Saved research workspace" }).locator("button[aria-pressed]");
        if (await leads.count()) {
          await leads.first().click();
          const brief = page.getByRole("region", { name: /^Research brief for/ });
          await brief.getByRole("heading").first().scrollIntoViewIfNeeded();
          await page.screenshot({ path: path.join(destination, `${stage}-lead-${label}.png`), fullPage: false, animations: "disabled" });
        }
      }
    }
  }
});
