// Menyalin berkas WASM MediaPipe dan mengunduh model Face Landmarker ke public/,
// supaya aplikasi tidak bergantung pada CDN saat demo.
import { cpSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const akar = join(dirname(fileURLToPath(import.meta.url)), '..');
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

cpSync(join(akar, 'node_modules/@mediapipe/tasks-vision/wasm'), join(akar, 'public/wasm'), {
  recursive: true,
});
console.log('WASM disalin ke public/wasm');

const tujuan = join(akar, 'public/model/face_landmarker.task');
if (existsSync(tujuan)) {
  console.log('Model sudah ada, tidak diunduh ulang');
} else {
  mkdirSync(dirname(tujuan), { recursive: true });
  try {
    const jawab = await fetch(MODEL_URL);
    if (!jawab.ok) throw new Error(`HTTP ${jawab.status}`);
    writeFileSync(tujuan, Buffer.from(await jawab.arrayBuffer()));
    console.log('Model diunduh ke public/model/face_landmarker.task');
  } catch (galat) {
    console.error(`Gagal mengunduh model (${galat.message}). Unduh manual:`);
    console.error(`  curl -L -o public/model/face_landmarker.task ${MODEL_URL}`);
    process.exitCode = 1;
  }
}
