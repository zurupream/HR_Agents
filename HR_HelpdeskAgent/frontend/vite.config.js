import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8080'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': { target: AGENT_URL, changeOrigin: true },
    },
  },
})
