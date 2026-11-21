// Real Chromium ↔ Vite proxy ↔ FastAPI ↔ PostgreSQL 16 integration.
// CI-only header session bypasses browser cookie flow; that has separate tests.
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const fixture=JSON.parse(readFileSync(process.env.SME_E2E_FIXTURE_PATH,'utf8'));
const origin='http://127.0.0.1:5173';
const browser=await chromium.launch({headless:true});

async function openWithToken(width,height,token) {
  const context=await browser.newContext({viewport:{width,height},
    extraHTTPHeaders:token?{'Authorization':'Bearer '+token}:{}});
  const page=await context.newPage();
  await page.goto(origin,{waitUntil:'domcontentloaded'});
  return {context,page};
}

try {
  for(const [width,height] of [[1440,900],[820,1180],[390,844],[320,640]]) {
    const {context,page}=await openWithToken(width,height,fixture.both_token);
    await page.getByText('Aichi NAS').waitFor({timeout:15000});
    assert.equal(await page.getByText('Aichi NAS').count(),1);
    assert.equal(await page.getByText('Owari Camera').count(),0);
    const options=await page.locator('select[aria-label="Select company"] option').allTextContents();
    assert.deepEqual(options,['Aichi Manufacturing','Owari Logistics']);
    await page.locator('select[aria-label="Select company"]').selectOption(fixture.tenant_b);
    await page.getByText('Owari Camera').waitFor({timeout:15000});
    assert.equal(await page.getByText('Aichi NAS').count(),0);
    assert.equal(await page.getByText('Owari Camera').count(),1);
    if(width <= 760) assert.equal(await page.locator('.mobileNav').isVisible(),true);
    else assert.equal(await page.locator('.sidebar').isVisible(),true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,
                 'unexpected horizontal overflow '+width);
    await context.close();
  }
  {
    const {context,page}=await openWithToken(390,844,null);
    await page.getByText('Unable to load workspace').waitFor({timeout:15000});
    assert.equal(await page.getByText('Aichi NAS').count(),0);
    await context.close();
  }
  {
    const {context,page}=await openWithToken(1440,900,fixture.only_a_token);
    await page.getByText('Aichi NAS').waitFor({timeout:15000});
    assert.deepEqual(await page.locator('select option').allTextContents(),['Aichi Manufacturing']);
    const forbidden=await context.request.get(origin+'/v1/tenants/'+fixture.tenant_b+'/assets');
    assert.equal(forbidden.status(),403);
    await context.close();
  }
  console.log('PASS: 4 viewports, tenant switching, denied session and cross-tenant HTTP.');
} finally {
  await browser.close();
}
