import { expect, test } from '@playwright/test';

const cors = { 'access-control-allow-origin': 'http://127.0.0.1:3100', 'access-control-allow-methods': 'GET,OPTIONS', 'access-control-allow-headers': 'content-type' };

test('customer search filters recorded accounts and competitors without changing data', async ({ page, request }) => {
  const response = await request.get('http://127.0.0.1:8011/api/living/workspace');
  expect(response.ok()).toBeTruthy();
  const workspace = await response.json();
  workspace.buyers = [
    { id: 1, buyer_name: 'Example Estates', sector: 'Hospitality', region: 'Yorkshire', estate_size: '', procurement_drivers: [], next_best_action: '' },
    { id: 2, buyer_name: 'Sample Trust', sector: 'Education', region: 'Wales', estate_size: '', procurement_drivers: [], next_best_action: '' },
  ];
  workspace.competitors = [{ id: 3, name: 'Example Security', sectors: ['Security'], strengths: [], weaknesses: [], pricing_behaviour: '', counter_strategy: '' }];
  await page.route('**/api/living/workspace', async (route) => route.request().method() === 'OPTIONS'
    ? route.fulfill({ status: 204, headers: cors }) : route.fulfill({ headers: cors, json: workspace }));
  await page.goto('/?view=accounts');
  const search = page.getByLabel('Search customer and competitor records');
  await expect(page.getByRole('heading', { name: 'Example Estates' })).toBeVisible();
  await search.fill('WALES');
  await expect(page.getByRole('heading', { name: 'Sample Trust' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Example Estates' })).toHaveCount(0);
  await search.fill('no match');
  await expect(page.getByRole('heading', { name: 'No matching customers' })).toBeVisible();
  await search.fill('example');
  await page.getByRole('tab', { name: /Competitor profiles/ }).click();
  await expect(page.getByRole('heading', { name: 'Example Security' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: 'Example Security' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});
