import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: { outDir: 'dist', assetsInlineLimit: 0, chunkSizeWarningLimit: 1000 },
  // Dev only: the Flask app (python src/trend_detective/app/web.py) serves /api/* on 127.0.0.1:5000.
  server: { proxy: { '/api': 'http://127.0.0.1:5000' } }
});
