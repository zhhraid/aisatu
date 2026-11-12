/** "M" = bibir mengatup (m, b, p). */
export type Bunyi = 'a' | 'i' | 'u' | 'o' | 'M';

export const SEMUA_BUNYI: readonly Bunyi[] = ['a', 'i', 'u', 'o', 'M'];

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
}

export type PosisiWajah = 'ok' | 'tidak_ada' | 'miring' | 'terlalu_jauh';
