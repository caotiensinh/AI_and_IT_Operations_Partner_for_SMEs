import {defineConfig,loadEnv} from "vite";
import {readFileSync} from "node:fs";
export default defineConfig(({mode})=>{
  const env=loadEnv(mode,".","DISCOVERY_");
  const target=env.DISCOVERY_API_ORIGIN;
  // Developer-only proxy; deployment MUST enforce same-origin TLS/auth independently.
  if(target && !/^https?:\/\/127\.0\.0\.1:\d+$/.test(target) &&
     !/^https?:\/\/localhost:\d+$/.test(target)){
    throw new Error("DISCOVERY_API_ORIGIN must be a loopback development endpoint");
  }
  return {server:{
    host:"127.0.0.1",
    https:env.DISCOVERY_TLS_CERT&&env.DISCOVERY_TLS_KEY?{
      cert:readFileSync(env.DISCOVERY_TLS_CERT),
      key:readFileSync(env.DISCOVERY_TLS_KEY)
    }:undefined,
    proxy:target?{
      "/v1":{target,changeOrigin:false},
      "/auth":{target,changeOrigin:false},
      ...(env.DISCOVERY_SYNTHETIC_IDP_ORIGIN?{
        "/oidc-test":{target:env.DISCOVERY_SYNTHETIC_IDP_ORIGIN,changeOrigin:false}
      }:{})
    }:undefined
  }};
});
