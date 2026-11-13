/// <reference types="vitest" />
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { cpSync, existsSync, readFileSync, statSync } from 'node:fs';
import { resolve, join, normalize } from 'node:path';

const DATA_DIR = resolve(__dirname, '../data');

/** Serves ../data at /data in dev, and copies it into the build output. */
function priceData(): Plugin {
  let outDir = 'dist';
  return {
    name: 'suki-price-data',
    configResolved(cfg) {
      outDir = resolve(cfg.root, cfg.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const base = server.config.base.replace(/\/$/, '');
        const url = (req.url ?? '').split('?')[0];
        if (!url.startsWith(`${base}/data/`)) return next();
        const rel = decodeURIComponent(url.slice(base.length + '/data/'.length));
        const file = normalize(join(DATA_DIR, rel));
        if (!file.startsWith(DATA_DIR) || !existsSync(file) || !statSync(file).isFile()) {
          res.statusCode = 404;
          return res.end('not found');
        }
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        res.end(readFileSync(file));
      });
    },
    closeBundle() {
      // vite-plugin-pwa runs a second build for the service worker; only copy into the app build.
      if (existsSync(DATA_DIR) && existsSync(join(outDir, 'index.html'))) {
        cpSync(DATA_DIR, join(outDir, 'data'), {
          recursive: true,
          // manifests are scraper bookkeeping, not app data
          filter: (src) => !src.endsWith('manifest.json'),
        });
      }
    },
  };
}

export default defineConfig({
  // GitHub Pages serves from /<repo>/; set BASE_PATH there. Other hosts use "/".
  base: process.env.BASE_PATH ?? '/',
  plugins: [
    react(),
    priceData(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      injectRegister: false,
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,woff2,svg,png,webmanifest}'],
      },
      manifest: {
        name: 'Suki — wet market prices',
        short_name: 'Suki',
        description: 'Which fish, pork, chicken and beef are a good buy today, from DA price reports.',
        display: 'standalone',
        start_url: '.',
        scope: '.',
        theme_color: '#0B5D51',
        background_color: '#F4F6F3',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
