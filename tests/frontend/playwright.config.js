// Run from the repo root (tooling lives in tests/frontend/.tmp, not globally):
//   node tests/frontend/.tmp/node_modules/@playwright/test/cli.js test --config tests/frontend/playwright.config.js
// Three groups: ui.spec.js runs against the mock API, and part1.spec.js and part2.spec.js against the real app (real_server.py).
const { defineConfig } = require('./.tmp/node_modules/@playwright/test');

const PORT = Number(process.env.UI_TEST_PORT) || 38917;
const REAL_PORT = Number(process.env.PART1_TEST_PORT) || 38927;

const shared = { channel: 'msedge', headless: true, viewport: { width: 1280, height: 800 } };

module.exports = defineConfig({
  testDir: __dirname,
  outputDir: `${__dirname}/.tmp/test-results-${PORT}`,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 30000,
  projects: [
    { name: 'mock', testMatch: /ui\.spec\.js$/, use: { ...shared, baseURL: `http://127.0.0.1:${PORT}` } },
    { name: 'part1', testMatch: /part1\.spec\.js$/, use: { ...shared, baseURL: `http://127.0.0.1:${REAL_PORT}` } },
    { name: 'part2', testMatch: /part2\.spec\.js$/, use: { ...shared, baseURL: `http://127.0.0.1:${REAL_PORT}` } },
    { name: 'locking', testMatch: /locking\.spec\.js$/, use: { ...shared, baseURL: `http://127.0.0.1:${REAL_PORT}` } },
  ],
  webServer: [
    {
      command: `python "${__dirname}/mock_api.py" --port ${PORT} --token dev-token`,
      url: `http://127.0.0.1:${PORT}/__mock/ping`,
      reuseExistingServer: false,
      stdout: 'ignore',
      timeout: 15000,
    },
    {
      command: `python "${__dirname}/real_server.py" --port ${REAL_PORT} --token dev-token`,
      url: `http://127.0.0.1:${REAL_PORT + 1}/control/ping`,
      reuseExistingServer: false,
      stdout: 'ignore',
      timeout: 20000,
    },
  ],
});
