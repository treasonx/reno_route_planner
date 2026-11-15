import preact from "@preact/preset-vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [preact()],
  build: { sourcemap: false, target: "es2022" },
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
} as Parameters<typeof defineConfig>[0]);
