import type { Blendshape, Fitur, PosisiWajah, Titik } from './tipe';

/** Hanya blendshape mulut dan rahang yang dipakai; alis dan mata diabaikan. */
export const BLENDSHAPE_MULUT = [
  'jawOpen',
  'mouthPucker',
  'mouthFunnel',
  'mouthSmileLeft',
  'mouthSmileRight',
  'mouthStretchLeft',
  'mouthStretchRight',
  'mouthPressLeft',
  'mouthPressRight',
  'mouthRollLower',
  'mouthRollUpper',
] as const;

// Indeks titik wajah MediaPipe.
const BIBIR_DALAM_ATAS = 13;
const BIBIR_DALAM_BAWAH = 14;
const DAHI = 10;
const DAGU = 152;
const HIDUNG = 1;
const TEPI_KIRI = 234;
const TEPI_KANAN = 454;

const MIN_TINGGI_WAJAH = 0.2; // bagian dari tinggi gambar
const MAKS_RASIO_MIRING = 2.2;

export function ambilBlendshape(
  kategori: readonly { categoryName: string; score: number }[],
): Blendshape {
  const hasil: Blendshape = {};
  for (const k of kategori) {
    if ((BLENDSHAPE_MULUT as readonly string[]).includes(k.categoryName)) {
      hasil[k.categoryName] = k.score;
    }
  }
  return hasil;
}

function jarak(a: Titik, b: Titik, lebar: number, tinggi: number): number {
  return Math.hypot((a.x - b.x) * lebar, (a.y - b.y) * tinggi);
}

function titik(daftar: readonly Titik[], indeks: number): Titik {
  const t = daftar[indeks];
  if (!t) throw new Error(`Titik wajah ${indeks} tidak ada`);
  return t;
}

/** Jarak bibir dalam atas-bawah dibagi tinggi wajah. Mendekati 0 saat bibir rapat. */
export function celahBibir(daftar: readonly Titik[], lebar: number, tinggi: number): number {
  const tinggiWajah = jarak(titik(daftar, DAHI), titik(daftar, DAGU), lebar, tinggi);
  if (tinggiWajah === 0) return 0;
  return (
    jarak(titik(daftar, BIBIR_DALAM_ATAS), titik(daftar, BIBIR_DALAM_BAWAH), lebar, tinggi) /
    tinggiWajah
  );
}

/** Wajah cukup dekat dan cukup menghadap kamera untuk dinilai. */
export function posisiWajah(daftar: readonly Titik[], lebar: number, tinggi: number): PosisiWajah {
  const tinggiWajah = jarak(titik(daftar, DAHI), titik(daftar, DAGU), lebar, tinggi);
  if (tinggiWajah < MIN_TINGGI_WAJAH * tinggi) return 'terlalu_jauh';
  const kiri = jarak(titik(daftar, HIDUNG), titik(daftar, TEPI_KIRI), lebar, tinggi);
  const kanan = jarak(titik(daftar, HIDUNG), titik(daftar, TEPI_KANAN), lebar, tinggi);
  const rasio = Math.max(kiri, kanan) / Math.max(Math.min(kiri, kanan), 1e-6);
  return rasio > MAKS_RASIO_MIRING ? 'miring' : 'ok';
}

/** Menghitung lima fitur dari blendshape saat ini, blendshape netral, dan celah bibir. */
export function hitungFitur(kini: Blendshape, netral: Blendshape, celah: number): Fitur {
  const d = (nama: string) => (kini[nama] ?? 0) - (netral[nama] ?? 0);
  const rata = (a: string, b: string) => (d(a) + d(b)) / 2;
  return {
    rahang: d('jawOpen'),
    bulat: Math.max(d('mouthPucker'), d('mouthFunnel')),
    lebar: Math.max(
      rata('mouthSmileLeft', 'mouthSmileRight'),
      rata('mouthStretchLeft', 'mouthStretchRight'),
    ),
    tekan: Math.max(
      rata('mouthPressLeft', 'mouthPressRight'),
      d('mouthRollLower'),
      d('mouthRollUpper'),
    ),
    celah,
    gulung: d('mouthRollLower') - d('mouthRollUpper'),
  };
}
