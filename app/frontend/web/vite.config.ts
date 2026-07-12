import { configDefaults, defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

export default defineConfig({
  // Router plugin must come before the React plugin.
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true }), react(), tailwindcss()],
  server: {
    proxy: {
      // Mirrors the deployment contract: the SPA calls /api/v1/*, the backend
      // mounts routes bare (see app/backend/src/fastapi_app/main.py:165).
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Playwright owns e2e/ — its *.spec.ts files must not run under vitest.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
