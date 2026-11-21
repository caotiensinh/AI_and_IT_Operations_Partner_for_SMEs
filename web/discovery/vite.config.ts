import { defineConfig } from "vite";
export default defineConfig({
  server: {
    host: "127.0.0.1",
    // A same-origin reverse proxy must publish /v1 behind an approved TLS/auth boundary.
    // No direct production backend URL or bearer credential is shipped in the bundle.
  }
});
