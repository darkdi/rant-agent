import tailwindcss from '@tailwindcss/postcss';
import vinext from 'vinext';
import { defineConfig } from 'vite';

export default defineConfig({
  css: { postcss: { plugins: [tailwindcss()] } },
  server: {
    host: '127.0.0.1', port: 4310, strictPort: true,
    proxy: { '/bridge': 'http://127.0.0.1:4311', '/auth': 'http://127.0.0.1:4311' },
  },
  plugins: [vinext({ nextConfig: { output: 'export' } })],
});
