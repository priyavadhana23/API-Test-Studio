import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy all /api calls to the FastAPI backend during development
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Raise the chunk-size warning threshold — Plotly alone is ~3 MB
    chunkSizeWarningLimit: 6000,
    rollupOptions: {
      output: {
        // Split vendor code into logical chunks for better caching
        manualChunks: {
          'react-vendor':  ['react', 'react-dom', 'react-router-dom'],
          'mui-vendor':    ['@mui/material', '@mui/icons-material', '@mui/x-data-grid',
                            '@emotion/react', '@emotion/styled'],
          'plotly-vendor': ['plotly.js-dist-min', 'react-plotly.js'],
          'axios':         ['axios'],
        },
      },
    },
  },
})
