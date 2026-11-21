import {describe,it,expect,vi,afterEach} from "vitest";
import {DiscoveryClient,normalizeError,validUuid} from "./api";

afterEach(()=>vi.unstubAllGlobals());
const config={tenantId:"123e4567-e89b-42d3-a456-426614174000",token:"example-only-token"};
describe("input and authorization boundary",()=>{
  it("validates actual UUIDs",()=>{
    expect(validUuid(config.tenantId)).toBe(true);
    expect(validUuid("../tenant")).toBe(false);
    expect(validUuid("")).toBe(false);
  });
  it("does not expose internal server response in user-visible errors",()=>{
    expect(normalizeError(403)).toContain("権限");
    expect(normalizeError(409)).toContain("競合");
  });
  it("sends tenant scoped same-origin API requests and bearer, without local storage",async()=>{
    const fake=vi.fn(async()=>({ok:true,json:async()=>({cases:[],next_cursor:null,limit:50})}));
    vi.stubGlobal("fetch",fake);
    await new DiscoveryClient(config).cases();
    expect(fake).toHaveBeenCalledOnce();
    const [url,options]=fake.mock.calls[0] as unknown as [string,RequestInit];
    expect(url).toBe("/v1/tenants/"+config.tenantId+"/research-cases?limit=50");
    expect((options.headers as Record<string,string>).Authorization).toBe("Bearer "+config.token);
    expect(options.cache).toBe("no-store");
  });
  it("retains idempotency key for a logical create request",async()=>{
    const fake=vi.fn(async()=>({ok:true,json:async()=>({case_id:"id"})}));
    vi.stubGlobal("fetch",fake);
    await new DiscoveryClient(config).createCase(config.tenantId,"Needs assessment","OTHER","same-key");
    const [,options]=fake.mock.calls[0] as unknown as [string,RequestInit];
    expect((options.headers as Record<string,string>)["Idempotency-Key"]).toBe("same-key");
  });
  it("does not permit false success on HTTP errors",async()=>{
    vi.stubGlobal("fetch",vi.fn(async()=>({ok:false,status:403})));
    await expect(new DiscoveryClient(config).cases()).rejects.toThrow("権限");
  });
  it("requests server-scoped sites without sending client-chosen role claims",async()=>{
    const fake=vi.fn(async()=>({ok:true,json:async()=>({
      sites:[{id:config.tenantId,label:"Synthetic office"}],next_cursor:null,limit:50
    })}));
    vi.stubGlobal("fetch",fake);
    const page=await new DiscoveryClient(config).sites();
    expect(page.sites).toHaveLength(1);
    const [url,options]=fake.mock.calls[0] as unknown as [string,RequestInit];
    expect(url).toBe("/v1/tenants/"+config.tenantId+"/discovery-sites?limit=50");
    expect(options.method).toBeUndefined();
    expect(options.body).toBeUndefined();
  });
  it("reads case-specific persisted source metadata with cursor",async()=>{
    const fake=vi.fn(async()=>({ok:true,json:async()=>({
      sources:[{id:config.tenantId,document_label:"Source",page:3}],
      next_cursor:null,limit:50
    })}));
    vi.stubGlobal("fetch",fake);
    const api=new DiscoveryClient(config);
    const page=await api.sources(config.tenantId,"123e4567-e89b-42d3-a456-426614174001");
    expect(page.sources[0].document_label).toBe("Source");
    const [url]=fake.mock.calls[0] as unknown as [string];
    expect(url).toContain("/research-cases/"+config.tenantId+"/sources?limit=50&after=");
  });
});
