import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('primary navigation and specialist tools remain keyboard accessible', async ({ page }) => {
  await page.goto('/?view=today');
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  const tools = nav.getByRole('button', { name: 'Tools' });
  await expect(tools).toHaveAttribute('aria-expanded', 'false');
  const scan = await new AxeBuilder({ page }).include('[aria-label="Main navigation"]').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(scan.violations.map((violation) => ({ id: violation.id, targets: violation.nodes.map((node) => node.target) }))).toEqual([]);
  await expect(nav.getByRole('button', { name: 'Finance' })).toBeHidden();
  await tools.focus();
  await page.keyboard.press('Enter');
  await expect(tools).toHaveAttribute('aria-expanded', 'true');
  await nav.getByRole('button', { name: 'Finance' }).click();
  await expect(page.getByRole('heading', { name: 'Understand the financial move.' })).toBeVisible();
  await page.reload();
  await expect(nav.getByRole('button', { name: 'Finance' })).toHaveAttribute('aria-current', 'page');
  await expect(tools).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('dialog', { name: 'Search and command' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Search or ask MiSi' })).toBeFocused();
  await page.keyboard.press('Escape');
});

test('mobile navigation opens, exposes tools and closes after navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?view=today');
  const toggle = page.getByRole('button', { name: 'Toggle navigation' });
  await toggle.click();
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await expect(nav.getByRole('button', { name: 'Discover' })).toBeVisible();
  await nav.getByRole('button', { name: 'Tools' }).click();
  await expect(nav.getByRole('button', { name: 'Finance' })).toBeVisible();
  await nav.getByRole('button', { name: 'Discover' }).click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('heading', { name: 'Discover opportunities' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
