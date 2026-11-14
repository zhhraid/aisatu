import { AMBANG_BAWAAN, kemiripan, nilaiBentuk, type Ambang, type Penilaian, type Petunjuk } from './aturan';
import { prediksi, type ModelBibir } from './model';
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
  /**
   * Model bibir personal anak ini. Kalau ada, bentuk bibir dinilai oleh model, bukan
   * aturan ambang (kecuali bibir rapat di dalam kata, dan bunyi yang tidak dilatih model).
   */
  model: ModelBibir | null;
}

/** Peluang minimal dari model supaya bentuk dianggap benar. */
export const PELUANG_MODEL_MIN = 0.6;

const PETUNJUK_BAWAAN: Partial<Record<Bunyi, Petunjuk>> = {
  a: 'buka_lebar', i: 'tarik_samping', u: 'kerucutkan', o: 'bulatkan',
  M: 'rapatkan', e: 'buka_sedikit', F: 'gigi_ke_bibir',
};

export const OPSI_PERCOBAAN: OpsiPercobaan = {
  tahanTunggalMs: 700,
  tahanVokalMs: 150,
  tahanKatupMs: 40,
  toleransiMs: 120,
  batasMs: 6000,
  maksDtMs: 200,
  tanpaSuara: false,
  model: null,
};

export interface FramePercobaan {
  /** Waktu dalam milidetik (misalnya performance.now()). */
  t: number;
  /** null kalau wajah tidak terlihat atau posisinya tidak layak dinilai. */
  fitur: Fitur | null;
  suara: boolean;
  /** Ada hembusan napas (untuk "h"). Kosong dianggap tidak ada. */
  napas?: boolean;
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
  petunjuk: Petunjuk | 'bersuara' | 'hembuskan' | 'desiskan' | null;
  sisaMs: number;
  /** 0 sampai 1, kemiripan bentuk bibir frame ini dengan bentuk target (untuk bilah "Kemiripan"). */
  kemiripan: number;
}

/** Bentuk yang dikirim ke backend (POST /ai/anak/{id}/percobaan), ditambah item_id. */
export interface HasilPercobaan {
  berhasil: boolean;
  langkah_tercapai: number;
  durasi_ms: number;
  /** 0 sampai 1, rata-rata kemiripan bentuk bibir selama percobaan ("Akurasi" di layar). */
  kemiripan: number;
  /** 1 sampai 3. Gagal tetap dapat 1 bintang supaya anak tidak patah semangat. */
  bintang: number;
  poin: number;
}

/** Bintang dari hasil: berhasil dan mirip (>= 80%) = 3, berhasil = 2, belum berhasil = 1. */
export function hitungBintang(berhasil: boolean, rataKemiripan: number): number {
  if (!berhasil) return 1;
  return rataKemiripan >= 0.8 ? 3 : 2;
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
  private jumlahKemiripan = 0;
  private kemiripanTerakhir = 0;
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
    // Bibir rapat dan huruf lidah (t, k, d) sangat singkat di dalam kata.
    return target === 'M' || target === 'T' ? this.opsi.tahanKatupMs : this.opsi.tahanVokalMs;
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
      kemiripan: this.kemiripanTerakhir,
    };
  }

  /** Penilaian bentuk dan kemiripan: dari model personal kalau tersedia, kalau tidak dari aturan. */
  private nilai(target: Bunyi, f: Fitur): { bentuk: Penilaian; mirip: number } {
    const dalamKata = !this.tunggal;
    const model = this.opsi.model;
    const pakaiModel = model && model.kelas.includes(target) && !(target === 'M' && dalamKata);
    if (!pakaiModel) {
      return { bentuk: nilaiBentuk(target, f, this.ambang, dalamKata), mirip: kemiripan(target, f, this.ambang, dalamKata) };
    }
    const tebak = prediksi(model, f);
    const peluang = tebak.bunyi === null ? 0 : (tebak.peluang[target] ?? 0);
    const cocok = tebak.bunyi === target && peluang >= PELUANG_MODEL_MIN;
    if (cocok) return { bentuk: { cocok: true, petunjuk: null }, mirip: 1 };
    const aturan = nilaiBentuk(target, f, this.ambang, dalamKata);
    return {
      bentuk: { cocok: false, petunjuk: aturan.petunjuk ?? PETUNJUK_BAWAAN[target] ?? null },
      mirip: Math.min(peluang, 0.95),
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
      this.kemiripanTerakhir = 0;
      return this.keadaan(false, frame.suara, null);
    }
    this.status = 'berjalan';
    this.aktifMs += dt;

    const target = this.urutan[this.langkah] as Bunyi;
    const { bentuk, mirip } = this.nilai(target, frame.fitur);
    this.kemiripanTerakhir = mirip;
    this.jumlahKemiripan += this.kemiripanTerakhir * dt;
    const suara = frame.suara || this.opsi.tanpaSuara;
    const napas = frame.napas || this.opsi.tanpaSuara;
    // "h" dinilai dari hembusan napas, bukan suara bernada. "f" boleh bersuara (v) atau
    // berupa hembusan (f). Di dalam kata, bibir mengatup tidak perlu bersuara (b dan p
    // memang senyap sesaat).
    // Desis (s, c, z) dikenali dari derau di mikrofon, seperti hembusan. Huruf lidah boleh
    // bersuara (d, n, l) atau berupa letupan tanpa suara (t, k).
    const perluNapas = target === 'H' || target === 'S';
    const perluSuara = !perluNapas && (this.tunggal || target !== 'M');
    const bunyiOk = perluNapas
      ? napas
      : !perluSuara || suara || ((target === 'F' || target === 'T') && napas);
    const ok = bentuk.cocok && bunyiOk;

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

    const petunjuk = !bentuk.cocok
      ? bentuk.petunjuk
      : bunyiOk
        ? null
        : target === 'S'
          ? 'desiskan'
          : perluNapas
            ? 'hembuskan'
            : 'bersuara';
    return this.keadaan(bentuk.cocok, suara, petunjuk);
  }

  /** Hasil akhir, atau null kalau percobaan belum selesai. */
  hasil(): HasilPercobaan | null {
    if (this.status !== 'berhasil' && this.status !== 'gagal') return null;
    const berhasil = this.status === 'berhasil';
    const rata =
      this.aktifMs > 0 ? this.jumlahKemiripan / this.aktifMs : this.kemiripanTerakhir;
    const bintang = hitungBintang(berhasil, rata);
    return {
      berhasil,
      langkah_tercapai: this.langkah,
      durasi_ms: Math.round(this.aktifMs),
      kemiripan: Math.round(rata * 100) / 100,
      bintang,
      poin: bintang * 10,
    };
  }
}
