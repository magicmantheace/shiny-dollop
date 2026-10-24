import { defineConfig } from 'vite';
import electron from 'vite-plugin-electron/simple';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
    electron({
      main: {
        entry: 'main/main.ts',
        vite: { build: { outDir: 'dist', emptyOutDir: false } },
      },
      preload: {
        input: 'preload/preload.ts',
        vite: { build: { outDir: 'dist', emptyOutDir: false } },
      },
    }),
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
});
