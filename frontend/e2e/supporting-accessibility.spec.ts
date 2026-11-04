import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

for (const view of ['accounts', 'opportunities', 'actions']) {
  test(`${view} page has accessible controls and contrast`, async ({ page }) => {
    await page.goto(`/?view=${view}`);
    await expect(page.locator('.m-support-light')).toBeVisible();
    const scan = await new AxeBuilder({ page }).include('.m-support-light').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(scan.violations.map((v) => ({ id:v.id, targets:v.nodes.map((n) => n.target) }))).toEqual([]);
  });
}
