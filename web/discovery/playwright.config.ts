import {defineConfig,devices} from "@playwright/test";
export default defineConfig({
  testDir:"./e2e",
  timeout:35_000,
  retries:0,
  use:{
    baseURL:"http://127.0.0.1:5173",
    trace:"retain-on-failure",
    screenshot:"only-on-failure",
    ...devices["Desktop Chrome"]
  },
  reporter:[["list"],["junit",{outputFile:"test-results/e2e-results.xml"}]],
  webServer:{
    command:"npm run dev -- --port 5173 --strictPort",
    url:"http://127.0.0.1:5173",
    reuseExistingServer:!process.env.CI,
    env:{"VITE_DISCOVERY_AUTH_MODE":"pilot"},
    timeout:40_000
  }
});
