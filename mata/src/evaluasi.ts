import { kemiripan, nilaiBentuk, type Ambang } from './aturan';
import { prediksi, type ModelBibir } from './model';
import { BENTUK_BIBIR, type Bunyi, type Fitur } from './tipe';

/** Tebakan aturan: bentuk yang lolos aturan (paling banyak satu, dijamin cekTumpang). */
export function tebakAturan(f: Fitur, ambang?: Ambang): Bunyi | null {
  return BENTUK_BIBIR.find((b) => nilaiBentuk(b, f, ambang).cocok) ?? null;
}

/** Tebakan model personal: kelas terdekat, atau null kalau tidak dikenali. */
export function tebakModel(f: Fitur, model: ModelBibir): Bunyi | null {
  return prediksi(model, f).bunyi;
}

/** Tebakan untuk satu rekaman: suara terbanyak dari tebakan tiap frame. */
export function tebakanTerbanyak(tebakan: readonly (Bunyi | null)[]): Bunyi | null {
  const hitung = new Map<Bunyi | null, number>();
  for (const t of tebakan) hitung.set(t, (hitung.get(t) ?? 0) + 1);
  let terbaik: Bunyi | null = null;
  let banyak = -1;
  for (const [t, n] of hitung) {
    if (n > banyak) [terbaik, banyak] = [t, n];
  }
  return terbaik;
}

/** Tabel kebingungan: target (yang diminta) x tebakan sistem. */
export class MatriksKebingungan {
  private readonly isi = new Map<string, Map<string, number>>();

  tambah(target: Bunyi, tebakan: Bunyi | null): void {
    const baris = this.isi.get(target) ?? new Map<string, number>();
    const kunci = tebakan ?? '?';
    baris.set(kunci, (baris.get(kunci) ?? 0) + 1);
    this.isi.set(target, baris);
  }

  get jumlah(): number {
    let n = 0;
    for (const baris of this.isi.values()) for (const v of baris.values()) n += v;
    return n;
  }

  /** Bagian rekaman yang ditebak benar, atau null kalau belum ada rekaman. */
  akurasi(): number | null {
    if (!this.jumlah) return null;
    let benar = 0;
    for (const [target, baris] of this.isi) benar += baris.get(target) ?? 0;
    return benar / this.jumlah;
  }

  perTarget(): { target: string; benar: number; jumlah: number }[] {
    return [...this.isi].map(([target, baris]) => ({
      target,
      benar: baris.get(target) ?? 0,
      jumlah: [...baris.values()].reduce((a, b) => a + b, 0),
    }));
  }

  /** Tabel teks dipisah tab: baris = target, kolom = tebakan ("?" = tidak dikenali). */
  keTsv(): string {
    const kolom = [...BENTUK_BIBIR, '?'].filter((k) =>
      [...this.isi.values()].some((b) => b.has(k)) || this.isi.has(k),
    );
    const baris = [['target \\ tebakan', ...kolom].join('\t')];
    for (const [target, isi] of this.isi) {
      baris.push([target, ...kolom.map((k) => String(isi.get(k) ?? 0))].join('\t'));
    }
    return baris.join('\n');
  }

  kosongkan(): void {
    this.isi.clear();
  }
}

/** Kemiripan untuk tampilan: dari model kalau ada, kalau tidak dari aturan. */
export function kemiripanGabungan(
  target: Bunyi,
  f: Fitur,
  ambang: Ambang | undefined,
  model: ModelBibir | null,
): number {
  if (model && model.kelas.includes(target)) return prediksi(model, f).peluang[target] ?? 0;
  return kemiripan(target, f, ambang);
}
