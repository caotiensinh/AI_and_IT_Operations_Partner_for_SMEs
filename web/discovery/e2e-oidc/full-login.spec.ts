import {test,expect} from "@playwright/test";
import {readFileSync} from "node:fs";

type Fixture={tenant:string;site:string;subject:string};
function fixture():Fixture{
  const path=process.env.SME_E2E_FIXTURE_PATH;
  if(!path)throw new Error("Synthetic OIDC fixture missing");
  return JSON.parse(readFileSync(path,"utf8")) as Fixture;
}

test("complete OIDC browser code + PKCE + RS256 → cookie tenant → logout → re-login",async({page,context})=>{
  const account=fixture();
  await page.goto("/");
  const login=page.getByRole("link",{name:"安全にログインする"});
  await expect(login).toBeVisible();
  await expect(login).toHaveAttribute("href","/auth/oidc/start");
  await login.click();
  // This follows an actual browser redirect through an isolated local IdP, a
  // one-use authorization code and the BFF's server-side code exchange.
  await expect(page.getByRole("button",{name:"Synthetic test tenant"})).toBeVisible();
  expect(await context.cookies()).toEqual(expect.arrayContaining([
    expect.objectContaining({name:"__Host-sme_session",secure:true,httpOnly:true}),
  ]));
  const exposed=await page.evaluate(()=>({
    cookie:document.cookie,
    local:Object.keys(localStorage),session:Object.keys(sessionStorage),
    location:window.location.href,
  }));
  expect(exposed.cookie).not.toContain("__Host-sme_session");
  expect(exposed.local).toEqual([]);
  expect(exposed.session).toEqual([]);
  expect(exposed.location).not.toContain("code=");
  expect(exposed.location).not.toContain("id_token=");
  await page.getByRole("button",{name:"Synthetic test tenant"}).click();
  await expect(page.getByRole("heading",{name:"調査案件",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"＋ 新規"}).click();
  await page.getByRole("combobox",{name:"対象拠点"}).selectOption(account.site);
  const label="OIDC signed flow "+Math.random().toString(36).slice(2,8);
  await page.getByLabel("案件名").fill(label);
  await page.getByRole("button",{name:"登録する"}).click();
  await expect(page.getByRole("heading",{name:label})).toBeVisible();
  await page.getByRole("button",{name:"ログアウト"}).click();
  await expect(page.getByRole("link",{name:"安全にログインする"})).toBeVisible();
  expect((await context.request.get("/auth/session/tenants")).status()).toBe(401);
  await page.getByRole("link",{name:"安全にログインする"}).click();
  await expect(page.getByRole("button",{name:"Synthetic test tenant"})).toBeVisible();
  await page.getByRole("button",{name:"Synthetic test tenant"}).click();
  await expect(page.getByRole("button",{name:new RegExp(label)})).toBeVisible();
});

test("replaying an already consumed authorization state and code is rejected",async({page,context})=>{
  let callback="";
  page.on("request",req=>{
    if(req.url().includes("/auth/oidc/callback?") && !callback)callback=req.url();
  });
  await page.goto("/");
  await page.getByRole("link",{name:"安全にログインする"}).click();
  await expect(page.getByRole("button",{name:"Synthetic test tenant"})).toBeVisible();
  expect(callback).toContain("state=");
  expect(callback).toContain("code=");
  const initialSession=(await context.cookies()).find(c=>c.name==="__Host-sme_session");
  expect(initialSession).toBeDefined();

  // Reuse the same state+code with an already-cleared browser binding.
  const replay=await context.request.get(callback,{maxRedirects:0});
  expect(replay.status()).toBe(401);
  const stillValid=await context.request.get("/auth/session/tenants");
  expect(stillValid.status()).toBe(200);

  // Confirm a forged callback cannot mint a new session after logout.
  const csrf=(await stillValid.json()).csrf_token as string;
  const logout=await context.request.post("/auth/session/logout",{
    headers:{"Origin":"https://127.0.0.1:5174","X-CSRF-Token":csrf}
  });
  expect(logout.status()).toBe(204);
  expect((await context.request.get("/auth/session/tenants")).status()).toBe(401);
  const secondReplay=await context.request.get(callback,{maxRedirects:0});
  expect(secondReplay.status()).toBe(401);
  expect((await context.request.get("/auth/session/tenants")).status()).toBe(401);
});
