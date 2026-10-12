import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // A fixed port of its own, so the app never drifts onto another port when a
  // different Vite project already holds 5173. The API only accepts this origin
  // (OTB_FRONTEND_ORIGINS), so a silent port change would break every request.
  server: { port: 5273, strictPort: true },
  preview: { port: 5273, strictPort: true },
})
