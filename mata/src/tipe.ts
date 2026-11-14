/**
 * Bentuk yang dinilai. "M" = bibir menutup (m, b, p), "F" = gigi atas ke bibir bawah (f, v),
 * "H" = hembusan napas (h), dinilai dari mikrofon. w dinilai sebagai "u", y sebagai "i".
 */
export type Bunyi = 'a' | 'i' | 'u' | 'o' | 'M' | 'e' | 'F' | 'H';

export const SEMUA_BUNYI: readonly Bunyi[] = ['a', 'i', 'u', 'o', 'M', 'e', 'F', 'H'];

/** Bentuk yang dinilai dari bibir (semua kecuali "H", yang dinilai dari suara napas). */
export const BENTUK_BIBIR: readonly Bunyi[] = ['a', 'i', 'u', 'o', 'M', 'e', 'F'];

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
