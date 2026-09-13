import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Production build output lands in ../dist, which we then publish at the repo root
// so GitHub Pages keeps serving a plain static root with zero config changes.
export default defineConfig({
  base: '/digital-solutions/',
  plugins: [react()],
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    sourcemap: false,
  },
});
