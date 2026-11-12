import { AMBANG_BAWAAN, nilaiBentuk, type Ambang, type Petunjuk } from './aturan';
import type { Bunyi, Fitur } from './tipe';

export interface OpsiPercobaan {
  /** Bunyi tunggal: bentuk benar dan bersuara harus ditahan selama ini. */
  tahanTunggalMs: number;
  /** Dalam suku kata atau kata: lama minimal tiap vokal. */
  tahanVokalMs: number;
  /** Dalam suku kata atau kata: lama minimal bibir mengatup (b/p sangat singkat). */
  tahanKatupMs: number;
  /** Bentuk boleh lepas sebentar tanpa mengulang hitungan tahan. */
  toleransiMs: number;
  /** Batas waktu satu percobaan, tidak menghitung waktu jeda. */
  batasMs: number;
  /** Selisih waktu antar-frame dibatasi, supaya frame yang tersendat tidak melompatkan hitungan. */
  maksDtMs: number;
  /** Abaikan syarat suara (untuk menguji bentuk bibir saja). */
  tanpaSuara: boolean;
}

export const OPSI_PERCOBAAN: OpsiPercobaan = {
  tahanTunggalMs: 700,
  tahanVokalMs: 150,
  tahanKatupMs: 40,
  toleransiMs: 120,
  batasMs: 6000,
  maksDtMs: 200,
  tanpaSuara: false,
};

export interface FramePercobaan {
  /** Waktu dalam milidetik (misalnya performance.now()). */
  t: number;
  /** null kalau wajah tidak terlihat atau posisinya tidak layak dinilai. */
  fitur: Fitur | null;
  suara: boolean;
}

export type StatusPercobaan = 'berjalan' | 'jeda' | 'berhasil' | 'gagal';

export interface Keadaan {
  status: StatusPercobaan;
  /** Indeks langkah yang sedang dikerjakan. */
  langkah: number;
  jumlahLangkah: number;
  target: Bunyi | null;
  cocok: boolean;
  suara: boolean;
  /** 0 sampai 1, kemajuan seluruh percobaan. */
  progres: number;
  petunjuk: Petunjuk | 'bersuara' | null;
  sisaMs: number;
}

/** Bentuk yang dikirim ke backend (POST /ai/anak/{id}/percobaan), ditambah item_id. */
export interface HasilPercobaan {
  berhasil: boolean;
  langkah_tercapai: number;
  durasi_ms: number;
}

/**
 * Menilai satu percobaan dari aliran frame. Tidak menyentuh kamera atau DOM,
 * jadi bisa diuji dengan frame buatan.
 */
export class Percobaan {
  private langkah = 0;
  private tahan = 0;
  private lepas = 0;
  private aktifMs = 0;
  private tSebelum: number | null = null;
  private status: StatusPercobaan = 'berjalan';
  private readonly opsi: OpsiPercobaan;

  constructor(
    private readonly urutan: readonly Bunyi[],
    private readonly ambang: Ambang = AMBANG_BAWAAN,
    opsi: Partial<OpsiPercobaan> = {},
  ) {
    if (urutan.length === 0) throw new Error('Urutan bunyi kosong');
    this.opsi = { ...OPSI_PERCOBAAN, ...opsi };
  }

  private get tunggal(): boolean {
    return this.urutan.length === 1;
  }

  private butuhTahan(target: Bunyi): number {
    if (this.tunggal) return this.opsi.tahanTunggalMs;
    return target === 'M' ? this.opsi.tahanKatupMs : this.opsi.tahanVokalMs;
  }

  private keadaan(cocok: boolean, suara: boolean, petunjuk: Keadaan['petunjuk']): Keadaan {
    const target = this.urutan[this.langkah] ?? null;
    const bagian = target ? Math.min(1, this.tahan / this.butuhTahan(target)) : 0;
    return {
      status: this.status,
      langkah: this.langkah,
      jumlahLangkah: this.urutan.length,
      target,
      cocok,
      suara,
      progres: Math.min(1, (this.langkah + bagian) / this.urutan.length),
      petunjuk,
      sisaMs: Math.max(0, this.opsi.batasMs - this.aktifMs),
    };
  }

  proses(frame: FramePercobaan): Keadaan {
    if (this.status === 'berhasil' || this.status === 'gagal') {
      return this.keadaan(false, frame.suara, null);
    }

    const dt =
      this.tSebelum === null ? 0 : Math.min(Math.max(frame.t - this.tSebelum, 0), this.opsi.maksDtMs);
    this.tSebelum = frame.t;

    if (!frame.fitur) {
      // Wajah hilang: waktu tidak berjalan dan percobaan tidak dihitung gagal.
      this.status = 'jeda';
      return this.keadaan(false, frame.suara, null);
    }
    this.status = 'berjalan';
    this.aktifMs += dt;

    const target = this.urutan[this.langkah] as Bunyi;
    const bentuk = nilaiBentuk(target, frame.fitur, this.ambang, !this.tunggal);
    const suara = frame.suara || this.opsi.tanpaSuara;
    // Di dalam kata, bibir mengatup tidak perlu bersuara (b dan p memang senyap sesaat).
    const perluSuara = this.tunggal || target !== 'M';
    const ok = bentuk.cocok && (!perluSuara || suara);

    if (ok) {
      this.tahan += dt;
      this.lepas = 0;
    } else {
      this.lepas += dt;
      if (this.lepas > this.opsi.toleransiMs) this.tahan = 0;
    }

    if (this.tahan >= this.butuhTahan(target)) {
      this.langkah += 1;
      this.tahan = 0;
      this.lepas = 0;
      if (this.langkah >= this.urutan.length) this.status = 'berhasil';
    } else if (this.aktifMs >= this.opsi.batasMs) {
      this.status = 'gagal';
    }

    const petunjuk = !bentuk.cocok ? bentuk.petunjuk : perluSuara && !suara ? 'bersuara' : null;
    return this.keadaan(bentuk.cocok, suara, petunjuk);
  }

  /** Hasil akhir, atau null kalau percobaan belum selesai. */
  hasil(): HasilPercobaan | null {
    if (this.status !== 'berhasil' && this.status !== 'gagal') return null;
    return {
      berhasil: this.status === 'berhasil',
      langkah_tercapai: this.langkah,
      durasi_ms: Math.round(this.aktifMs),
    };
  }
}
