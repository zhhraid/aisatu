/**
 * Bentuk yang dinilai. "m" = bibir menutup (m, b, p), "f" = gigi atas ke bibir bawah (f, v),
 * "h" = hembusan napas (h), dinilai dari mikrofon. w dinilai sebagai "u", y sebagai "i".
 * Huruf lidah dinilai SEBAGIAN (posisi mulut dan suaranya, bukan lidah):
 * "s" = desis (s, c, x, z, j), "t" = huruf lidah lain (t, d, n, l, r, k, g, q).
 */
export type Bunyi = 'a' | 'i' | 'u' | 'o' | 'm' | 'e' | 'f' | 'h' | 's' | 't';

export const SEMUA_BUNYI: readonly Bunyi[] = ['a', 'i', 'u', 'o', 'm', 'e', 'f', 'h', 's', 't'];

/** Bunyi yang hanya dinilai sebagian karena kamera tidak bisa melihat lidah. */
export const DINILAI_SEBAGIAN: readonly Bunyi[] = ['s', 't'];

/** Bentuk yang dinilai penuh dari bibir (tanpa "h" yang dari napas, dan tanpa huruf lidah). */
export const BENTUK_BIBIR: readonly Bunyi[] = ['a', 'i', 'u', 'o', 'm', 'e', 'f'];

/** Nilai blendshape MediaPipe per nama, 0 sampai 1. */
export type Blendshape = Record<string, number>;

export interface Titik {
  x: number;
  y: number;
}

/**
 * Lima angka yang dipakai aturan bentuk bibir. Semua kecuali `celah` adalah
 * selisih dari wajah netral anak; `celah` adalah jarak bibir mutlak.
 */
export interface Fitur {
  /** Seberapa terbuka rahang. */
  rahang: number;
  /** Bibir mengerucut atau membulat. */
  bulat: number;
  /** Bibir melebar ke samping. */
  lebar: number;
  /** Bibir saling menekan. */
  tekan: number;
  /** Jarak bibir dalam atas ke bawah, dibagi tinggi wajah. */
  celah: number;
  /**
   * Bibir bawah tergulung ke dalam lebih dari bibir atas (mouthRollLower - mouthRollUpper),
   * tanda gigi atas menempel di bibir bawah seperti pada f/v. Kosong dianggap 0.
   */
  gulung?: number;
}

export type PosisiWajah = 'ok' | 'tidak_ada' | 'miring' | 'terlalu_jauh';
