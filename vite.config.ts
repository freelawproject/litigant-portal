import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  base: '/static/',

  build: {
    manifest: true,
    outDir: resolve(__dirname, 'staticfiles'),
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'frontend/src/ts/main.ts'),
        styles: resolve(__dirname, 'frontend/src/css/input.css'),
      },
      output: {
        // Organize output files
        entryFileNames: 'js/[name]-[hash].js',
        chunkFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) {
            return 'css/[name]-[hash][extname]'
          }
          return 'assets/[name]-[hash][extname]'
        },
      },
    },
  },

  server: {
    host: 'localhost',
    port: 5173,
    origin: 'http://localhost:5173',
    strictPort: true,
  },

  resolve: {
    alias: {
      '@': resolve(__dirname, 'frontend/src'),
    },
  },
})
