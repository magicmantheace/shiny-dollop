import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

// Two renderer windows: the pet itself and the care panel.
export default defineConfig({
  plugins: [react()],
  // The rigged pet model ships as a bundled asset URL (PetArt3D).
  assetsInclude: ['**/*.glb'],
  root: path.join(here, 'src', 'renderer'),
  base: './',
  build: {
    outDir: path.join(here, 'dist', 'renderer'),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        pet: path.join(here, 'src', 'renderer', 'pet.html'),
        panel: path.join(here, 'src', 'renderer', 'panel.html'),
      },
    },
  },
  server: {
    port: 5180,
    strictPort: true,
  },
});
