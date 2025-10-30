import { defineConfig } from 'vitest/config'
import { resolve } from 'path'

export default defineConfig({
  test: {
    globals: true,
    environment: 'happy-dom',
    include: ['frontend/src/**/*.{test,spec}.{ts,js}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['frontend/src/**/*.{ts,js}'],
      exclude: [
        'frontend/src/**/*.{test,spec}.{ts,js}',
        'frontend/src/**/*.d.ts',
        'frontend/src/types/**/*',
      ],
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'frontend/src'),
    },
  },
})
