import { defineConfig } from 'vite';

// Kamera butuh HTTPS atau localhost. Untuk uji di HP lewat jaringan lokal,
// pakai tunnel HTTPS atau deploy ke hosting statis.
export default defineConfig({
  server: { port: 5173 },
});
