import { BENTUK_BIBIR, type Bunyi, type Fitur } from './tipe';

/**
 * Model bibir personal: classifier nearest centroid yang dilatih dari contoh bentuk bibir
 * SATU anak (dikumpulkan saat Setel otomatis, sekitar 2 detik per bentuk). Tiap bentuk
 * diwakili titik tengahnya; jarak diukur setelah tiap ciri dibagi sebaran gabungannya,
 * sehingga ciri yang bergerak kecil (celah) setara dengan yang bergerak besar (rahang).
 *
 * Kecil, cepat, bisa dilatih di browser dalam milidetik, dan disimpan sebagai JSON.
 */
export interface ModelBibir {
  versi: 1;
  kelas: Bunyi[];
  /** Titik tengah tiap kelas, dalam ruang ciri yang belum dinormalkan. */
  pusat: number[][];
  /** Sebaran gabungan tiap ciri (simpangan baku di dalam kelas), untuk normalisasi. */
  skala: number[];
  /** Jumlah contoh per kelas saat dilatih. */
  jumlah: number[];
  /** Akurasi validasi silang saat dilatih (0 sampai 1), kalau dihitung. */
  akurasi?: number;
  /** Berapa kali model diperbarui dari latihan setelah dilatih. */
  pembaruan?: number;
}

/**
 * Model hanya dipakai kalau akurasi validasi silangnya minimal ini. Model dari contoh yang
 * buruk (bentuk tidak dibedakan saat Setel otomatis) lebih buruk daripada aturan ambang.
 */
export const AKURASI_MODEL_MIN = 0.8;

export function layakDipakai(model: ModelBibir | null): boolean {
  return model !== null && (model.akurasi ?? 0) >= AKURASI_MODEL_MIN;
}

export interface Prediksi {
  /** Kelas terdekat, atau null kalau bentuknya jauh dari semua kelas (misalnya wajah diam). */
  bunyi: Bunyi | null;
  /** Peluang tiap kelas (softmax dari jarak), jumlahnya 1. */
  peluang: Partial<Record<Bunyi, number>>;
  /** Jarak ke kelas terdekat, dalam satuan simpangan baku. */
  jarak: number;
}

/** Celah dikali 5 supaya rentangnya setara ciri lain sebelum dihitung sebarannya. */
export function vektor(f: Fitur): number[] {
  return [f.rahang, f.bulat, f.lebar, f.tekan, f.celah * 5, f.gulung ?? 0];
}

const SKALA_MIN = 0.03;
/** Lebih jauh dari ini (dalam simpangan baku) dari semua kelas: tidak dikenali. */
export const JARAK_ASING = 4;

export function latihModel(contoh: Partial<Record<Bunyi, readonly Fitur[]>>): ModelBibir {
  const kelas = BENTUK_BIBIR.filter((b) => (contoh[b]?.length ?? 0) > 0);
  if (kelas.length < 2) throw new Error('Butuh contoh minimal dua bentuk');
  const data = kelas.map((b) => contoh[b]!.map(vektor));
  const dimensi = data[0]![0]!.length;
  const pusat = data.map((baris) =>
    Array.from({ length: dimensi }, (_, j) => baris.reduce((s, v) => s + v[j]!, 0) / baris.length),
  );
  const skala = Array.from({ length: dimensi }, (_, j) => {
    let jumlah = 0;
    let n = 0;
    data.forEach((baris, k) => {
      for (const v of baris) {
        jumlah += (v[j]! - pusat[k]![j]!) ** 2;
        n++;
      }
    });
    return Math.max(Math.sqrt(jumlah / Math.max(n - kelas.length, 1)), SKALA_MIN);
  });
  return { versi: 1, kelas, pusat, skala, jumlah: data.map((b) => b.length) };
}

function jarakKuadrat(v: number[], pusat: number[], skala: number[]): number {
  return v.reduce((s, x, j) => s + ((x - pusat[j]!) / skala[j]!) ** 2, 0);
}

export function prediksi(model: ModelBibir, f: Fitur): Prediksi {
  const v = vektor(f);
  const d2 = model.pusat.map((p) => jarakKuadrat(v, p, model.skala));
  const terkecil = Math.min(...d2);
  const bobot = d2.map((d) => Math.exp(-(d - terkecil) / 2));
  const total = bobot.reduce((a, b) => a + b, 0);
  const peluang: Partial<Record<Bunyi, number>> = {};
  model.kelas.forEach((b, i) => (peluang[b] = bobot[i]! / total));
  const jarak = Math.sqrt(terkecil);
  return { bunyi: jarak > JARAK_ASING ? null : model.kelas[d2.indexOf(terkecil)]!, peluang, jarak };
}

export interface HasilValidasi {
  /** Bagian contoh yang ditebak benar saat contoh itu tidak ikut melatih (leave-one-out). */
  akurasi: number;
  perKelas: Partial<Record<Bunyi, number>>;
  /** matriks[target][tebakan] = jumlah; tebakan "?" = tidak dikenali. */
  matriks: Record<string, Record<string, number>>;
  jumlah: number;
}

/**
 * Validasi silang leave-one-out: tiap contoh ditebak oleh model yang dilatih tanpa contoh
 * itu. Ini perkiraan akurasi model untuk anak ini, tanpa butuh data uji terpisah.
 */
export function validasiSilang(contoh: Partial<Record<Bunyi, readonly Fitur[]>>): HasilValidasi {
  const kelas = BENTUK_BIBIR.filter((b) => (contoh[b]?.length ?? 0) > 0);
  const matriks: Record<string, Record<string, number>> = {};
  let benar = 0;
  let total = 0;
  const benarKelas: Partial<Record<Bunyi, number>> = {};
  for (const target of kelas) {
    const daftar = contoh[target]!;
    daftar.forEach((f, i) => {
      const tanpa = { ...contoh, [target]: daftar.filter((_, j) => j !== i) };
      const model = latihModel(tanpa);
      const tebakan = prediksi(model, f).bunyi ?? '?';
      matriks[target] ??= {};
      matriks[target][tebakan] = (matriks[target][tebakan] ?? 0) + 1;
      total++;
      if (tebakan === target) {
        benar++;
        benarKelas[target] = (benarKelas[target] ?? 0) + 1;
      }
    });
  }
  const perKelas: Partial<Record<Bunyi, number>> = {};
  for (const b of kelas) perKelas[b] = (benarKelas[b] ?? 0) / contoh[b]!.length;
  return { akurasi: total ? benar / total : 0, perKelas, matriks, jumlah: total };
}

/** Memeriksa JSON model dari penyimpanan sebelum dipakai. */
export function bacaModel(data: unknown): ModelBibir | null {
  const m = data as Partial<ModelBibir> | null;
  if (!m || m.versi !== 1 || !Array.isArray(m.kelas) || !Array.isArray(m.pusat) || !Array.isArray(m.skala)) {
    return null;
  }
  if (m.kelas.length !== m.pusat.length || m.pusat.some((p) => p.length !== m.skala!.length)) return null;
  // Model lama memakai kode huruf besar (M, F); kini semua huruf kecil.
  return { ...(m as ModelBibir), kelas: m.kelas.map((b) => String(b).toLowerCase() as Bunyi) };
}

/** Melatih model sekaligus mengukur akurasinya dengan validasi silang. */
export function latihDanValidasi(contoh: Partial<Record<Bunyi, readonly Fitur[]>>): {
  model: ModelBibir;
  validasi: HasilValidasi;
} {
  const validasi = validasiSilang(contoh);
  return { model: { ...latihModel(contoh), akurasi: Math.round(validasi.akurasi * 1000) / 1000 }, validasi };
}

/** Contoh baru hanya dipakai kalau model sudah yakin dan bentuknya dekat dengan yang dikenal. */
export const PELUANG_BELAJAR_MIN = 0.8;
export const JARAK_BELAJAR_MAKS = 2.5;
/** Bobot contoh baru paling kecil 1/60: model berubah pelan, tidak terbawa satu percobaan. */
const JENDELA_BELAJAR = 60;

/**
 * Belajar terus dari latihan: menggeser titik tengah satu bentuk ke arah contoh baru dari
 * percobaan yang berhasil. Mengembalikan model baru, atau null kalau contoh ditolak (model
 * belum yakin, atau bentuknya jauh dari yang dikenal) supaya model tidak belajar hal salah.
 */
export function perbaruiModel(model: ModelBibir, bunyi: Bunyi, f: Fitur): ModelBibir | null {
  const k = model.kelas.indexOf(bunyi);
  if (k < 0) return null;
  const t = prediksi(model, f);
  if (t.bunyi !== bunyi || (t.peluang[bunyi] ?? 0) < PELUANG_BELAJAR_MIN) return null;
  const v = vektor(f);
  const d = Math.sqrt(v.reduce((s, x, j) => s + ((x - model.pusat[k]![j]!) / model.skala[j]!) ** 2, 0));
  if (d > JARAK_BELAJAR_MAKS) return null;
  const n = (model.jumlah[k] ?? 0) + 1;
  const bobot = 1 / Math.min(n, JENDELA_BELAJAR);
  const pusat = model.pusat.map((p, i) => (i === k ? p.map((x, j) => x + bobot * (v[j]! - x)) : p));
  const jumlah = model.jumlah.map((x, i) => (i === k ? n : x));
  return { ...model, pusat, jumlah, pembaruan: (model.pembaruan ?? 0) + 1 };
}
