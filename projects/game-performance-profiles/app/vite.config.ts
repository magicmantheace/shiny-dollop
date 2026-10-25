import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist/renderer',
    emptyOutDir: false,
    target: 'chrome120',
    minify: false,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
