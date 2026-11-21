import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      port: Number(process.env.PORT || 5173),
      strictPort: true,
      proxy: {
        "/api/v1/auth": {
          target: env.AUTH_PROXY_TARGET || "http://127.0.0.1:8002",
          changeOrigin: true,
        },
        "/api/v1": {
          target: env.AGENT_PROXY_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
          timeout: 180000,
          proxyTimeout: 180000,
        },
      },
    },
  };
});
