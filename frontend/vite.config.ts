import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // amazon-cognito-identity-js is published for Node and reaches for `global`,
  // which browsers do not define — without this the bundle throws on load.
  define: {
    global: 'globalThis',
  },
})
