import { expect, test } from '@playwright/test';
const headers = { 'access-control-allow-origin': 'http://127.0.0.1:3100', 'access-control-allow-methods': 'GET,POST,PATCH,OPTIONS', 'access-control-allow-headers': 'content-type' };

test('review an evidence-linked suggestion and prepare a research brief without submitting', async ({page}) => {
  const requests: string[] = [];
  await page.route('**/api/market-network/**', async route => {
    const req=route.request(); const path=new URL(req.url()).pathname; requests.push(`${req.method()} ${path}`);
    if (req.method()==='OPTIONS') return route.fulfill({status:204,headers});
    if (path.endsWith('/summary')) return route.fulfill({headers,json:{companies:0,verified_companies:0,awards:0,source_records:1,source_revisions:1,sources:[],limitations:[]}});
    if (path.endsWith('/opportunities/1/review')) return route.fulfill({headers,json:{id:1,review_state:'investigate'}});
    if (path.endsWith('/opportunities')) return route.fulfill({headers,json:{total:1,items:[{id:1,state:'suggested',review_state:'unreviewed',suggestion:{kind:'possible_renewal_window',customer:'Example Council',title:'Fire alarm maintenance',supplier:'Example Ltd',timing:'2027-08-01',observation:'A published end date exists.',commercial_relevance:'Review the scope.',inference:'There may be a renewal window.',unknowns:['Current service and extensions.'],next_action:'Verify before engagement.',evidence:[{source_revision_id:1,source_url:'https://example.org/notice',source_key:'test',record_key:'one',published_at:'2026-01-01',fields:['contracts[0]']}]}}]}});
    return route.fulfill({headers,json:{items:[],total:0}});
  });
  await page.goto('/?view=discover');
  const network=page.getByRole('region',{name:'Fire and security market intelligence'});
  await network.getByText('Explore the market network').click();
  await network.getByText('Commercial suggestions to verify').click();
  await network.getByText('Example Council · Fire alarm maintenance').click();
  await expect(network.getByText('Current service and extensions.')).toBeVisible();
  await network.getByRole('button',{name:'Investigate',exact:true}).click();
  await expect(network.getByText('Your review: investigate. Preparing a brief does not start research or contact anyone.')).toBeVisible();
  await network.getByRole('button',{name:'Prepare research brief'}).click();
  await expect(page.getByLabel('Research brief', { exact: true })).toHaveValue(/Example Council/);
  expect(requests.some(path => path.includes('universal-research-jobs'))).toBe(false);
});
