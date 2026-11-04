import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Demo-only fixtures are fetched from an isolated SQLite API; no real records are altered.
test('populated customer, opportunity and action views remain usable and legible', async ({ page, request }) => {
  test.skip(!process.env.MISI_QA_DEMO_URL, 'Requires an explicitly configured isolated demo API.');
  const demoUrl = process.env.MISI_QA_DEMO_URL;
  await page.route('**/api/living/**', async (route) => {
    const input = route.request();
    if (input.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': 'http://127.0.0.1:3100', 'access-control-allow-methods': 'GET,OPTIONS', 'access-control-allow-headers': 'content-type' } });
    if (input.method() !== 'GET') return route.abort();
    const url = new URL(input.url());
    const response = await request.get(`${demoUrl}${url.pathname}${url.search}`);
    return route.fulfill({ status: response.status(), headers: { 'access-control-allow-origin': 'http://127.0.0.1:3100', 'content-type': 'application/json' }, body: await response.body() });
  });
  for (const view of ['accounts', 'opportunities', 'actions']) {
    await page.goto(`/?view=${view}`);
    const content = page.locator('.m-support-light');
    await expect(content).toBeVisible();
    if (view === 'accounts') {
      const buyer = content.locator('article').filter({ hasText: 'Alderwick University' });
      await expect(buyer).toBeVisible();
      await expect(buyer.getByText('Consolidate planned maintenance and evidence reporting')).toBeVisible();
      await expect(buyer.getByRole('button', { name: /Integrated campus fire & security/ })).toBeVisible();
    }
    if (view === 'opportunities') {
      await expect(content.getByRole('button', { name: 'Integrated campus fire & security' })).toBeVisible();
      await content.getByLabel('Filter opportunities').fill('Alderwick');
      await expect(content.getByText('1 records')).toBeVisible();
    }
    if (view === 'actions') {
      await expect(content.getByText('Confirm engineering capacity and review the scope with the account owner').first()).toBeVisible();
      await content.getByRole('button', { name: /Continue/ }).first().click();
      await expect(page.getByRole('dialog', { name: 'Continue action' })).toBeVisible();
      await page.keyboard.press('Escape');
    }
    const scan = await new AxeBuilder({ page }).include('.m-support-light').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(scan.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
    await page.setViewportSize({ width: 1024, height: 768 });
    const heading = await content.locator('.m-heading h1').boundingBox();
    const body = await content.boundingBox();
    expect(Math.abs(heading!.x - body!.x), `${view} header alignment`).toBeLessThan(2);
    await page.setViewportSize({ width: 390, height: 844 });
    const widths = await page.evaluate(() => Object.fromEntries(['html', 'body', '.m-workspace', '.m-shell-main', '.m-main', '.m-support-light', '.m-table-scroll'].map((selector) => { const node = document.querySelector(selector); const rect = node?.getBoundingClientRect(); return [selector, node ? { width: rect?.width, right: rect?.right, scroll: node.scrollWidth, client: node.clientWidth, overflow: getComputedStyle(node).overflowX } : null]; })));
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `${view} page overflow: ${JSON.stringify(widths)}`).toBe(false);
    if (view === 'opportunities') {
      const table = content.locator('.m-table-scroll');
      expect(await table.evaluate((e) => e.scrollWidth > e.clientWidth && getComputedStyle(e).overflowX === 'auto')).toBe(true);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
  }
});
