/** Typed same-origin discovery client. Tokens are intentionally memory-only. */
export type Case = { id:string; site_id:string; label:string; company_code:string; status:string };
export type Evidence = { document_label:string; page:number } | null;
export type Requirement = { id:string; statement:string; classification:"explicit"|"inferred"|"unverified"; approval_state:"proposed"|"confirmed"|"rejected"; source:Evidence };
export type Review = { version:number; previous_state:string; next_state:string; rationale:string; reviewer_id:string; reviewed_at:string };
export type ReviewHistory = { approval_state:string; review_version:number; reviews:Review[] };
export type Page<T> = { limit:number; next_cursor:string|null } & T;
export type CasePage = Page<{cases:Case[]}>;
export type RequirementPage = Page<{requirements:Requirement[]}>;
export type Config = {tenantId:string; token:string};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export function validUuid(value:string):boolean { return UUID.test(value); }
export function normalizeError(status:number):string {
  if(status===401) return "認証情報がありません。セッションを確認してください。";
  if(status===403) return "この操作への権限がありません。";
  if(status===404) return "対象が存在しないか、表示権限がありません。";
  if(status===409) return "他の変更と競合しました。最新状態を確認してください。";
  if(status===422) return "入力値または承認条件を確認してください。";
  return "通信またはサーバー処理に失敗しました。";
}
export class DiscoveryClient {
  constructor(private readonly config: Config) {}
  async request<T>(route:string, init:RequestInit={}):Promise<T> {
    const response=await fetch("/v1/tenants/"+encodeURIComponent(this.config.tenantId)+route,{
      ...init,
      cache:"no-store",
      headers:{"Authorization":"Bearer "+this.config.token,"Accept":"application/json",
        ...(init.body?{"Content-Type":"application/json"}:{}),...init.headers}
    });
    if(!response.ok) throw new Error(normalizeError(response.status));
    return (await response.json()) as T;
  }
  cases(after:string|null=null):Promise<CasePage>{
    return this.request("/research-cases?limit=50"+(after?"&after="+encodeURIComponent(after):""));
  }
  requirements(caseId:string,after:string|null=null):Promise<RequirementPage>{
    return this.request("/research-cases/"+caseId+"/requirements?limit=50"+
      (after?"&after="+encodeURIComponent(after):""));
  }
  createCase(site_id:string,label:string,company_code:string,key:string){
    return this.request<{case_id:string}>("/research-cases",{
      method:"POST",headers:{"Idempotency-Key":key},
      body:JSON.stringify({site_id,label,company_code})
    });
  }
  addSource(caseId:string,source_id:string,document_label:string,page:number) {
    return this.request<{source_id:string}>("/research-cases/"+caseId+"/sources",{
      method:"POST",body:JSON.stringify({source_id,document_label,page})
    });
  }
  addRequirement(caseId:string,requirement_id:string,statement:string,classification:string,source_id:string|null){
    return this.request<{requirement_id:string}>("/research-cases/"+caseId+"/requirements",{
      method:"POST",body:JSON.stringify({requirement_id,statement,classification,source_id})
    });
  }
  history(caseId:string,requirementId:string) {
    return this.request<ReviewHistory>("/research-cases/"+caseId+"/requirements/"+requirementId+"/reviews");
  }
  review(caseId:string,requirementId:string,expected_version:number,decision:string,rationale:string){
    return this.request<{review_version:number;approval_state:string;updated:boolean}>(
      "/research-cases/"+caseId+"/requirements/"+requirementId+"/review",{
        method:"POST",body:JSON.stringify({expected_version,decision,rationale})
      });
  }
}
