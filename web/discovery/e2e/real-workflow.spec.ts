import {test,expect} from "@playwright/test";
import {readFileSync} from "node:fs";

type Fixture={tenant:string;site:string;token:string};
function getFixture():Fixture {
  const path=process.env.SME_E2E_FIXTURE_PATH;
  if(!path)throw new Error("SME_E2E_FIXTURE_PATH is mandatory; do not use mocks");
  return JSON.parse(readFileSync(path,"utf8")) as Fixture;
}

test("real PostgreSQL: create case → source → explicit requirement → review → history",async({page})=>{
  const fixture=getFixture();
  const name="合成テスト調査 "+Math.random().toString(36).slice(2,9);
  await page.goto("/");
  await page.getByLabel("Tenant UUID").fill(fixture.tenant);
  await page.getByLabel("セッショントークン").fill(fixture.token);
  await page.getByRole("button",{name:"接続する"}).click();
  await expect(page.getByRole("heading",{name:"調査案件",exact:true})).toBeVisible();

  await page.getByRole("button",{name:"＋ 新規"}).click();
  await page.getByLabel("Site UUID").fill(fixture.site);
  await page.getByLabel("案件名").fill(name);
  await page.getByRole("button",{name:"登録する"}).click();
  await expect(page.getByRole("heading",{name})).toBeVisible();

  await page.getByRole("tab",{name:"根拠資料を登録"}).click();
  await page.getByLabel("資料の表示名").fill("合成テスト出典");
  await page.getByLabel("ページ番号").fill("3");
  await page.getByRole("button",{name:"資料情報を登録"}).click();
  await expect(page.getByText("合成テスト出典",{exact:true})).toBeVisible();
  const sourceLine=page.locator(".source-row").filter({hasText:"合成テスト出典"});
  const line=await sourceLine.locator("small").innerText();
  const sourceId=line.match(/[a-f0-9]{8}-[a-f0-9-]{27,}/i)?.[0];
  expect(sourceId,"new metadata source UUID must be rendered").toBeTruthy();

  await page.getByRole("tab",{name:"要件管理"}).click();
  await page.getByLabel("課題・期待する成果").fill("現場の手入力を削減したい");
  await page.getByLabel("根拠レベル").selectOption("explicit");
  await page.getByLabel("出典 UUID（明示の場合必須）").fill(sourceId!);
  await page.getByRole("button",{name:"要件を登録"}).click();
  await expect(page.getByRole("button",{name:/現場の手入力を削減したい/})).toBeVisible();
  await page.getByRole("button",{name:/現場の手入力を削減したい/}).click();
  await expect(page.getByRole("heading",{name:"審査履歴"})).toBeVisible();

  await page.getByLabel("判断").selectOption("confirmed");
  await page.getByLabel("理由（8文字以上）").fill("出典の3ページで確認済み");
  await page.getByRole("button",{name:"審査を保存"}).click();
  await expect(page.getByText("出典の3ページで確認済み")).toBeVisible();
  await expect(page.getByText("バージョン 1")).toBeVisible();
  await expect(page.locator(".state.confirmed")).toHaveCount(1);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("invalid session cannot enter workspace",async({page})=>{
  const fixture=getFixture();
  await page.goto("/");
  await page.getByLabel("Tenant UUID").fill(fixture.tenant);
  await page.getByLabel("セッショントークン").fill("A".repeat(43));
  await page.getByRole("button",{name:"接続する"}).click();
  await expect(page.getByRole("alert")).toContainText("権限");
  await expect(page.getByRole("heading",{name:"調査案件",exact:true})).toHaveCount(0);
});
