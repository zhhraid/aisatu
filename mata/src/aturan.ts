import type { Bunyi, Fitur } from './tipe';

/**
 * Ambang aturan bentuk bibir. Angka ini titik awal yang ditebak, belum disetel
 * dengan wajah sungguhan. Setel lewat halaman demo, lalu salin hasilnya ke sini.
 */
export interface Ambang {
  a: { rahangMin: number; bulatMaks: number };
  i: { lebarMin: number; rahangMaks: number; bulatMaks: number };
  u: { bulatMin: number; rahangMaks: number };
  o: { bulatMin: number; rahangMin: number; rahangMaks: number };
  M: { celahMaks: number; rahangMaks: number; tekanMin: number; bulatMaks: number };
}

export const AMBANG_BAWAAN: Ambang = {
  a: { rahangMin: 0.45, bulatMaks: 0.3 },
  i: { lebarMin: 0.3, rahangMaks: 0.2, bulatMaks: 0.15 },
  u: { bulatMin: 0.4, rahangMaks: 0.2 },
  o: { bulatMin: 0.3, rahangMin: 0.2, rahangMaks: 0.5 },
  // tekanMin 0: bibir rapat sudah cukup. Naikkan kalau bibir diam terlalu mudah lolos.
  // bulatMaks: bibir yang mengerucut rapat (bentuk "u") tidak dihitung mengatup.
  M: { celahMaks: 0.02, rahangMaks: 0.15, tekanMin: 0, bulatMaks: 0.3 },
};

export type Petunjuk =
  | 'buka_lebar'
  | 'buka_sedikit'
  | 'tutup_sedikit'
  | 'jangan_bulatkan'
  | 'tarik_samping'
  | 'kerucutkan'
  | 'bulatkan'
  | 'rapatkan';

export const TEKS_PETUNJUK: Record<Petunjuk, string> = {
  buka_lebar: 'Buka mulut lebih lebar',
  buka_sedikit: 'Buka mulut sedikit',
  tutup_sedikit: 'Jangan terlalu terbuka',
  jangan_bulatkan: 'Jangan bulatkan bibir',
  tarik_samping: 'Tarik bibir ke samping',
  kerucutkan: 'Kerucutkan bibir',
  bulatkan: 'Bulatkan bibir',
  rapatkan: 'Rapatkan bibir',
};

export interface Penilaian {
  cocok: boolean;
  /** Syarat pertama yang belum terpenuhi, untuk ditampilkan sebagai ikon petunjuk. */
  petunjuk: Petunjuk | null;
}

const COCOK: Penilaian = { cocok: true, petunjuk: null };
const kurang = (petunjuk: Petunjuk): Penilaian => ({ cocok: false, petunjuk });

/**
 * Menilai apakah bentuk bibir saat ini cocok dengan bunyi yang diminta.
 *
 * `dalamKata`: bibir mengatup di dalam suku kata atau kata boleh sambil membulat,
 * karena pada "bu" atau "mo" bibir memang sudah bersiap untuk vokal berikutnya.
 */
export function nilaiBentuk(
  bunyi: Bunyi,
  f: Fitur,
  ambang: Ambang = AMBANG_BAWAAN,
  dalamKata = false,
): Penilaian {
  switch (bunyi) {
    case 'a': {
      const t = ambang.a;
      if (f.rahang < t.rahangMin) return kurang('buka_lebar');
      if (f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      return COCOK;
    }
    case 'i': {
      const t = ambang.i;
      if (f.rahang >= t.rahangMaks) return kurang('tutup_sedikit');
      if (f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      if (f.lebar < t.lebarMin) return kurang('tarik_samping');
      return COCOK;
    }
    case 'u': {
      const t = ambang.u;
      if (f.bulat < t.bulatMin) return kurang('kerucutkan');
      if (f.rahang >= t.rahangMaks) return kurang('tutup_sedikit');
      return COCOK;
    }
    case 'o': {
      const t = ambang.o;
      if (f.bulat < t.bulatMin) return kurang('bulatkan');
      if (f.rahang < t.rahangMin) return kurang('buka_sedikit');
      if (f.rahang > t.rahangMaks) return kurang('tutup_sedikit');
      return COCOK;
    }
    case 'M': {
      const t = ambang.M;
      if (f.celah > t.celahMaks || f.rahang > t.rahangMaks || f.tekan < t.tekanMin) {
        return kurang('rapatkan');
      }
      if (!dalamKata && f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      return COCOK;
    }
  }
}

// ------------------------------------------------------------- kemiripan

/** Seberapa dekat nilai ke syarat "minimal": 1 kalau sudah memenuhi. */
function dekatMin(nilai: number, min: number): number {
  if (min <= 0) return 1;
  return Math.max(0, Math.min(1, nilai / min));
}

/** Seberapa dekat nilai ke syarat "maksimal": 1 kalau sudah memenuhi, turun linear sesudahnya. */
function dekatMaks(nilai: number, maks: number): number {
  if (nilai <= maks) return 1;
  const rentang = Math.max(maks, 0.1);
  return Math.max(0, 1 - (nilai - maks) / rentang);
}

/**
 * Kemiripan bentuk bibir saat ini dengan bentuk target, 0 sampai 1, dihitung dari
 * angka yang sama dengan aturan. Bernilai 1 hanya kalau aturannya terpenuhi,
 * jadi angka ini dan keping hijau tidak pernah bertentangan.
 */
export function kemiripan(
  bunyi: Bunyi,
  f: Fitur,
  ambang: Ambang = AMBANG_BAWAAN,
  dalamKata = false,
): number {
  let bagian: number[];
  switch (bunyi) {
    case 'a':
      bagian = [dekatMin(f.rahang, ambang.a.rahangMin), dekatMaks(f.bulat, ambang.a.bulatMaks)];
      break;
    case 'i':
      bagian = [
        dekatMin(f.lebar, ambang.i.lebarMin),
        dekatMaks(f.rahang, ambang.i.rahangMaks),
        dekatMaks(f.bulat, ambang.i.bulatMaks),
      ];
      break;
    case 'u':
      bagian = [dekatMin(f.bulat, ambang.u.bulatMin), dekatMaks(f.rahang, ambang.u.rahangMaks)];
      break;
    case 'o':
      bagian = [
        dekatMin(f.bulat, ambang.o.bulatMin),
        dekatMin(f.rahang, ambang.o.rahangMin),
        dekatMaks(f.rahang, ambang.o.rahangMaks),
      ];
      break;
    case 'M':
      bagian = [
        dekatMaks(f.celah, ambang.M.celahMaks),
        dekatMaks(f.rahang, ambang.M.rahangMaks),
        dekatMin(f.tekan, ambang.M.tekanMin),
        dalamKata ? 1 : dekatMaks(f.bulat, ambang.M.bulatMaks),
      ];
      break;
  }
  // Rata-rata geometris: satu syarat yang jauh meleset menurunkan nilai, tidak
  // tertutupi syarat lain yang kebetulan terpenuhi.
  const rata = Math.pow(
    bagian.reduce((a, b) => a * b, 1),
    1 / bagian.length,
  );
  // 100% disisakan untuk bentuk yang benar-benar lolos aturan.
  return nilaiBentuk(bunyi, f, ambang, dalamKata).cocok ? 1 : Math.min(rata, 0.95);
}

const VOKAL = new Set(['a', 'i', 'u', 'o']);
const BILABIAL = new Set(['m', 'b', 'p']);

/**
 * Urutan bentuk bibir yang terlihat dari sebuah kata. Konsonan selain m/b/p
 * dilewati dan dua bentuk sama yang berurutan digabung. Sama dengan aturan di backend.
 */
export function urutanDariTeks(teks: string): Bunyi[] {
  const hasil: Bunyi[] = [];
  for (const huruf of teks.toLowerCase()) {
    let bentuk: Bunyi | null = null;
    if (VOKAL.has(huruf)) bentuk = huruf as Bunyi;
    else if (BILABIAL.has(huruf)) bentuk = 'M';
    if (bentuk && hasil[hasil.length - 1] !== bentuk) hasil.push(bentuk);
  }
  return hasil;
}
