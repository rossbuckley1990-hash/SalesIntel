import { test } from '@playwright/test';
import path from 'node:path';

test('capture actual workspace screens for local design review', async ({ page }) => {
  const stage = process.env.MISI_DESIGN_STAGE || 'after';
  const folder = path.resolve(process.cwd(), process.env.MISI_DESIGN_ROOT || '../design-review', stage);
  for (const [size, width, height] of [['desktop',1440,900],['tablet',1024,768],['mobile',390,844]] as const) {
    await page.setViewportSize({ width, height });
    for (const [name, view] of [['home','today'],['discover','discover'],['customers','accounts'],['actions','actions'],['opportunities','opportunities']] as const) {
      await page.goto(`/?view=${view}`, { waitUntil: 'networkidle' });
      await page.screenshot({ path: path.join(folder,`${name}-${size}.png`), animations:'disabled' });
      if (name === 'discover') {
        const leads = page.getByRole('region',{name:'Saved research workspace'}).locator('button[aria-pressed]');
        if (await leads.count()) {
          await leads.first().click();
          const brief = page.getByRole('region',{name:/^Research brief for/});
          await brief.getByRole('heading').first().scrollIntoViewIfNeeded();
          await page.screenshot({ path: path.join(folder,`lead-${size}.png`), animations:'disabled' });
        }
      }
    }
  }
  if (stage === 'after') {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/?view=today', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: /Search or ask SalesIntel/ }).click();
    await page.getByRole('dialog', { name: 'Search and command' }).waitFor();
    await page.screenshot({ path: path.join(folder, 'search-interaction-desktop.png'), animations: 'disabled' });
  }
});
