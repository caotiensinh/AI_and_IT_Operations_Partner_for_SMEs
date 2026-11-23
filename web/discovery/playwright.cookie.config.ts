import {defineConfig,devices} from "@playwright/test";
export default defineConfig({
  testDir:"./e2e-cookie",
  timeout:45_000,
  retries:0,
  reporter:[["list"],["junit",{outputFile:"test-results/cookie-e2e-results.xml"}]],
  use:{
    ...devices["Desktop Chrome"],
    baseURL:"https://127.0.0.1:5174",
    ignoreHTTPSErrors:true,
    trace:"retain-on-failure",
    screenshot:"only-on-failure",
  },
  webServer:{
    command:"npm run dev -- --port 5174 --strictPort",
    url:"https://127.0.0.1:5174",
    ignoreHTTPSErrors:true,
    reuseExistingServer:false,
    env:{VITE_DISCOVERY_AUTH_MODE:"cookie",
      DISCOVERY_API_ORIGIN:"http://127.0.0.1:8001"},
    timeout:40_000,
  }
});
