import {describe,it,expect,vi,afterEach} from "vitest";
import {DiscoveryClient,discoverBrowserSession,logoutBrowserSession,normalizeError,validUuid} from "./api";

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
  it("browser-cookie API never adds Authorization and includes CSRF on mutations",async()=>{
    const fake=vi.fn(async()=>({ok:true,json:async()=>({case_id:"synthetic"})}));
    vi.stubGlobal("fetch",fake);
    await new DiscoveryClient({tenantId:config.tenantId,csrfToken:"csrf-value"})
      .createCase(config.tenantId,"Synthetic","OTHER","synthetic-idempotency-key");
    const [,options]=fake.mock.calls[0] as unknown as [string,RequestInit];
    const headers=options.headers as Record<string,string>;
    expect(headers.Authorization).toBeUndefined();
    expect(headers["X-CSRF-Token"]).toBe("csrf-value");
    expect(options.credentials).toBe("same-origin");
  });
  it("session bootstrap and logout never return or require opaque bearer",async()=>{
    const calls=vi.fn()
      .mockResolvedValueOnce({ok:true,json:async()=>({
        tenants:[{id:config.tenantId,label:"Synthetic"}],csrf_token:"csrf-token"
      })})
      .mockResolvedValueOnce({ok:true,status:204});
    vi.stubGlobal("fetch",calls);
    const session=await discoverBrowserSession();
    expect(session?.tenants[0].label).toBe("Synthetic");
    await logoutBrowserSession(session!.csrf_token);
    const [url,options]=calls.mock.calls[1] as [string,RequestInit];
    expect(url).toBe("/auth/session/logout");
    expect((options.headers as Record<string,string>)["X-CSRF-Token"]).toBe("csrf-token");
    expect((options.headers as Record<string,string>).Authorization).toBeUndefined();
  });
  it("no cookie session is a normal signed-out state",async()=>{
    vi.stubGlobal("fetch",vi.fn(async()=>({ok:false,status:401})));
    await expect(discoverBrowserSession()).resolves.toBeNull();
  });
});
