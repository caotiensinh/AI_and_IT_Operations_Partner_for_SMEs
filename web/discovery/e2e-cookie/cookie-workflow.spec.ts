import {test,expect} from "@playwright/test";
import {readFileSync} from "node:fs";

type Fixture={tenant:string;site:string;token:string};
function fixture():Fixture{
  const path=process.env.SME_E2E_FIXTURE_PATH;
  if(!path)throw new Error("SME_E2E_FIXTURE_PATH is required");
  return JSON.parse(readFileSync(path,"utf8")) as Fixture;
}
const origin="https://127.0.0.1:5174";
async function issueExistingSyntheticSession(context:import("@playwright/test").BrowserContext){
  const value=fixture().token;
  await context.addCookies([{
    name:"__Host-sme_session",value,url:origin,
    secure:true,httpOnly:true,sameSite:"Lax"
  }]);
}

test("HTTPS cookie mode: select tenant, create, source, approve, logout",async({page,context})=>{
  const seeded=fixture();
  await page.goto("/");
  await expect(page.getByRole("link",{name:"安全にログインする"})).toBeVisible();
  await issueExistingSyntheticSession(context);
  await page.reload();
  await expect(page.getByRole("heading",{name:"事業所の選択"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Synthetic test tenant"})).toBeVisible();
  const exposed=await page.evaluate(()=>({
    local:Object.keys(localStorage),session:Object.keys(sessionStorage),
    cookie:document.cookie
  }));
  expect(exposed.local).toEqual([]);
  expect(exposed.session).toEqual([]);
  expect(exposed.cookie).not.toContain("__Host-sme_session");
  await page.getByRole("button",{name:"Synthetic test tenant"}).click();
  await expect(page.getByRole("heading",{name:"調査案件",exact:true})).toBeVisible();

  const name="Cookie HTTPS 調査 "+Math.random().toString(36).slice(2,8);
  await page.getByRole("button",{name:"＋ 新規"}).click();
  await page.getByRole("combobox",{name:"対象拠点"}).selectOption(seeded.site);
  await page.getByLabel("案件名").fill(name);
  await page.getByRole("button",{name:"登録する"}).click();
  await expect(page.getByRole("heading",{name})).toBeVisible();

  await page.getByRole("tab",{name:"根拠資料を登録"}).click();
  await page.getByLabel("資料の表示名").fill("合成 Cookie 原本");
  await page.getByLabel("ページ番号").fill("2");
  await page.getByRole("button",{name:"資料情報を登録"}).click();
  await expect(page.getByText("合成 Cookie 原本",{exact:true})).toBeVisible();
  const sourceLine=await page.locator(".source-row").filter({hasText:"合成 Cookie 原本"})
    .locator("small").innerText();
  const source=sourceLine.match(/[a-f0-9]{8}-[a-f0-9-]{27,}/i)?.[0];
  expect(source).toBeTruthy();

  await page.getByRole("tab",{name:"要件管理"}).click();
  await page.getByLabel("課題・期待する成果").fill("合成資料に基づく入力削減");
  await page.getByLabel("根拠レベル").selectOption("explicit");
  await page.getByRole("combobox",{name:"出典資料（明示の場合必須）"}).selectOption(source!);
  await page.getByRole("button",{name:"要件を登録"}).click();
  await page.getByRole("button",{name:/合成資料に基づく入力削減/}).click();
  await expect(page.getByRole("heading",{name:"審査履歴"})).toBeVisible();
  await page.getByLabel("判断").selectOption("confirmed");
  await page.getByLabel("理由（8文字以上）").fill("資料2ページの記載を確認した");
  await page.getByRole("button",{name:"審査を保存"}).click();
  await expect(page.getByText("資料2ページの記載を確認した")).toBeVisible();
  await expect(page.getByText("バージョン 1")).toBeVisible();

  const cookies=await context.cookies(origin);
  expect(cookies.find(c=>c.name==="__Host-sme_session")?.httpOnly).toBe(true);
  expect(cookies.find(c=>c.name==="__Host-sme_session")?.secure).toBe(true);
  await page.getByRole("button",{name:"ログアウト"}).click();
  await expect(page.getByRole("link",{name:"安全にログインする"})).toBeVisible();
  const after=await context.request.get(origin+"/auth/session/tenants");
  expect(after.status()).toBe(401);
});

test("HTTPS cookie mode denies forged writes without CSRF and wrong Origin",async({page,context})=>{
  const seeded=fixture();
  await issueExistingSyntheticSession(context);
  await page.goto("/");
  await expect(page.getByRole("button",{name:"Synthetic test tenant"})).toBeVisible();
  const session=await context.request.get(origin+"/auth/session/tenants");
  expect(session.status()).toBe(200);
  const csrf=(await session.json()).csrf_token as string;
  const url=origin+"/v1/tenants/"+seeded.tenant+"/research-cases";
  const body={site_id:seeded.site,label:"CSRF rejection synthetic",company_code:"OTHER"};
  const key="synthetic-csrf-denial-1234";
  const none=await context.request.post(url,{data:body,headers:{"Idempotency-Key":key}});
  expect(none.status()).toBe(403);
  const attacker=await context.request.post(url,{data:body,headers:{
    "Idempotency-Key":key,"Origin":"https://attacker.example","X-CSRF-Token":csrf
  }});
  expect(attacker.status()).toBe(403);
  const bearer=await context.request.post(url,{data:body,headers:{
    "Idempotency-Key":key,"Origin":origin,"X-CSRF-Token":csrf,
    "Authorization":"Bearer "+seeded.token
  }});
  expect(bearer.status()).toBe(400);
  const cases=await context.request.get(origin+"/v1/tenants/"+seeded.tenant+"/research-cases");
  expect(cases.ok()).toBeTruthy();
  expect(JSON.stringify(await cases.json())).not.toContain("CSRF rejection synthetic");
});
