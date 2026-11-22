import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom", include: ["tests/*.component.test.tsx"],
    coverage: { provider: "v8", reporter: ["text", "json-summary", "cobertura"], reportsDirectory: "../reports/frontend-coverage", include: ["src/**/*.{ts,tsx}"], exclude: ["src/**/*.test.ts", "src/main.tsx", "src/types.ts"] },
    setupFiles: ["tests/setup.ts"], maxWorkers: 1,
  },
});
