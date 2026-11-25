import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Im Dev-Modus laufen Vite (5173) und FastAPI (8000) getrennt; /api wird durchgereicht.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist", sourcemap: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
