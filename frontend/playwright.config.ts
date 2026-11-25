import { defineConfig, devices } from "@playwright/test";

/**
 * Layouttests gegen den echten Build. Der Server (tests/e2e/server.py) startet die App
 * mit Temp-Datenbank und Fake-Portalen, also ohne Netzwerk und ohne echte Daten.
 * Vorher `npm run build`, damit frontend/dist aktuell ist.
 */
const PORT = Number(process.env.E2E_PORT ?? 8766);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "off",
    // Kartenkacheln kämen von openstreetmap.org: im Test bewusst offline.
    serviceWorkers: "block",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `uv run --offline python -m tests.e2e.server --port ${PORT}`,
    cwd: "..",
    url: `http://127.0.0.1:${PORT}/api/postings`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { NO_PROXY: "127.0.0.1,localhost", no_proxy: "127.0.0.1,localhost" },
  },
});
