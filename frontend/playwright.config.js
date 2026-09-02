import { defineConfig, devices } from '@playwright/test'

const apiPort = process.env.QUIZ_E2E_PORT || '28765'
const frontendPort = process.env.QUIZ_FRONTEND_PORT || '15173'
const python = process.env.QUIZ_PYTHON || 'python'

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    browserName: 'chromium',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: `${python} tests/e2e_server.py`,
      cwd: '..',
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: { QUIZ_E2E_PORT: apiPort },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      cwd: '.',
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: { VITE_QUIZ_SESSION: 'e2e-session', VITE_API_TARGET: `http://127.0.0.1:${apiPort}` },
    },
  ],
})
