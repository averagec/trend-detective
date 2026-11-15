import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: { outDir: 'dist', assetsInlineLimit: 0, chunkSizeWarningLimit: 1000 },
  // npm run dev: send the analysis API to Flask (python src/trend_detective/app/web.py)
  server: { proxy: { '/api': 'http://127.0.0.1:5000' } }
});
