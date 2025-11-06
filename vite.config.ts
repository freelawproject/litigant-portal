import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  base: '/static/',

  build: {
    manifest: true,
    outDir: resolve(__dirname, 'staticfiles'),
    // Generate source maps for debugging
    sourcemap: true,
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
    host: '0.0.0.0', // Allow external connections (needed for ngrok)
    port: 5173,
    origin: process.env.VITE_ORIGIN || 'http://localhost:5173',
    strictPort: true,
    // Allow all hosts (needed for ngrok dynamic URLs)
    allowedHosts: ['.ngrok-free.dev', '.ngrok.io', '.ngrok-free.app'],
    // Allow ngrok and other external hosts
    hmr: {
      protocol: 'ws',
      host: process.env.VITE_HMR_HOST || 'localhost',
      port: 5173,
    },
  },

  resolve: {
    alias: {
      '@': resolve(__dirname, 'frontend/src'),
    },
  },
})
