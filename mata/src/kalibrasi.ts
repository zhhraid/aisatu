import type { Blendshape } from './tipe';

export interface OpsiKalibrasi {
  durasiMs: number;
  minFrame: number;
  /** Simpangan baku jawOpen terbesar yang masih dianggap diam. */
  maksGoyang: number;
  /** jawOpen rata-rata terbesar yang masih dianggap mulut tertutup. */
  maksTerbuka: number;
}

export const OPSI_KALIBRASI: OpsiKalibrasi = {
  durasiMs: 2000,
  minFrame: 15,
  maksGoyang: 0.08,
  maksTerbuka: 0.3,
};

export type HasilKalibrasi =
  | { ok: true; netral: Blendshape }
  | { ok: false; alasan: 'wajah_tidak_terlihat' | 'banyak_bergerak' | 'mulut_terbuka' };

/** Mengumpulkan wajah netral selama beberapa detik, lalu merata-ratakannya. */
export class Kalibrasi {
  private mulai: number | null = null;
  private terakhir = 0;
  private readonly frame: Blendshape[] = [];

  constructor(private readonly opsi: OpsiKalibrasi = OPSI_KALIBRASI) {}

  /** `blend` null kalau wajah tidak terlihat atau posisinya tidak layak dinilai. */
  tambah(t: number, blend: Blendshape | null): void {
    this.mulai ??= t;
    this.terakhir = t;
    if (blend) this.frame.push(blend);
  }

  progres(): number {
    if (this.mulai === null) return 0;
    return Math.min(1, (this.terakhir - this.mulai) / this.opsi.durasiMs);
  }

  selesai(): boolean {
    return this.progres() >= 1;
  }

  hasil(): HasilKalibrasi {
    if (this.frame.length < this.opsi.minFrame) return { ok: false, alasan: 'wajah_tidak_terlihat' };

    const netral: Blendshape = {};
    for (const nama of Object.keys(this.frame[0] ?? {})) {
      netral[nama] = this.frame.reduce((jumlah, f) => jumlah + (f[nama] ?? 0), 0) / this.frame.length;
    }

    const rahang = this.frame.map((f) => f['jawOpen'] ?? 0);
    const rata = netral['jawOpen'] ?? 0;
    const simpangan = Math.sqrt(
      rahang.reduce((jumlah, v) => jumlah + (v - rata) ** 2, 0) / rahang.length,
    );
    if (simpangan > this.opsi.maksGoyang) return { ok: false, alasan: 'banyak_bergerak' };
    if (rata > this.opsi.maksTerbuka) return { ok: false, alasan: 'mulut_terbuka' };
    return { ok: true, netral };
  }
}
