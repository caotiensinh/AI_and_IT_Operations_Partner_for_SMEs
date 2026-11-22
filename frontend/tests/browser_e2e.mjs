// Real Chromium ↔ Vite proxy ↔ FastAPI ↔ PostgreSQL 16 integration.
// CI-only header session bypasses browser cookie flow; that has separate tests.
import { chromium } from 'playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const fixture=JSON.parse(readFileSync(process.env.SME_E2E_FIXTURE_PATH,'utf8'));
const origin='http://127.0.0.1:5173';
const browser=await chromium.launch({headless:true});
const evidenceDir=process.env.SME_E2E_SCREENSHOT_DIR;
const captures=[];
if(evidenceDir) mkdirSync(evidenceDir,{recursive:true});
async function capture(page,name,width,height) {
  if(!evidenceDir) return;
  const bytes=await page.screenshot({path:join(evidenceDir,name+'.png'),fullPage:false,animations:'disabled'});
  assert.equal(bytes.subarray(1,4).toString('ascii'),'PNG','PNG signature missing');
  const actualWidth=bytes.readUInt32BE(16), actualHeight=bytes.readUInt32BE(20);
  assert.equal(actualWidth,width,'screenshot width mismatch');
  assert.equal(actualHeight,height,'screenshot height mismatch');
  assert.ok(bytes.length>=5000,'screenshot unexpectedly small or blank');
  captures.push({
    name,file:name+'.png',viewport:{width,height},
    actual_png:{width:actualWidth,height:actualHeight,bytes:bytes.length,
      sha256:createHash('sha256').update(bytes).digest('hex')},
    source:'live Chromium/Vite/FastAPI/PostgreSQL with disposable synthetic CI fixture'
  });
}

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
    await capture(page,'overview-'+width+'x'+height,width,height);
    const visibleNav=width<=760?'.mobileNav':'.sidebar';
    await page.locator(visibleNav).getByRole('button',{name:'Assets',exact:true}).click();
    await page.getByText('Company assets').waitFor({timeout:15000});
    await page.getByText('Aichi NAS').waitFor({timeout:15000});
    await capture(page,'assets-'+width+'x'+height,width,height);
    await page.locator(visibleNav).getByRole('button',{name:'Overview',exact:true}).click();
    await page.getByText('Your operations at a glance').waitFor({timeout:15000});
    const options=await page.locator('select[aria-label="Select company"] option').allTextContents();
    assert.deepEqual(options,['Aichi Manufacturing','Owari Logistics']);
    await page.locator('select[aria-label="Select company"]').selectOption(fixture.tenant_b);
    await page.getByText('Owari Camera').waitFor({timeout:15000});
    assert.equal(await page.getByText('Aichi NAS').count(),0);
    assert.equal(await page.getByText('Owari Camera').count(),1);
    // Aichi and Owari metrics are deliberately distinct synthetic CI data.
    await page.locator(visibleNav).getByRole('button',{name:'Monitoring'}).click();
    await page.getByText('owari-telemetry').waitFor({timeout:15000});
    assert.equal(await page.getByText('aichi-telemetry').count(),0);
    await page.locator('select[aria-label="Select company"]').selectOption(fixture.tenant_a);
    await page.getByText('aichi-telemetry').waitFor({timeout:15000});
    assert.equal(await page.getByText('owari-telemetry').count(),0);
    await capture(page,'monitoring-'+width+'x'+height,width,height);
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
    await capture(page,'unauthorized-390x844',390,844);
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
  if(evidenceDir) {
    writeFileSync(join(evidenceDir,'manifest.json'),JSON.stringify({
      evidence_type:'INTEGRATION_TEST_NOT_USER_ACCEPTANCE',
      synthetic_data:true,
      idp:'CI header-token bypass; not real OIDC browser login',
      production_ready:false,
      source_sha:process.env.CI_SOURCE_SHA||'not-set',
      acceptance_status:'UNREVIEWED',
      archival_status:'NOT_VERIFIED',
      capture_integrity_verified:true,
      expected_screen_count:13,
      actual_screen_count:captures.length,
      screens:captures
    },null,2));
    assert.equal(captures.length,13,'expected 12 screen/viewport captures plus unauthorized state');
  }
  console.log('PASS: 4 viewports, tenant switching, denied session, cross-tenant HTTP and labelled screenshots.');
} finally {
  await browser.close();
}
