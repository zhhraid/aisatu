import type { Bunyi, Fitur } from './tipe';

/**
 * Ambang aturan bentuk bibir. Semua angka kecuali celah adalah selisih blendshape
 * MediaPipe dari wajah netral anak (0 sampai 1).
 */
export interface Ambang {
  a: { rahangMin: number; bulatMaks: number };
  i: { lebarMin: number; rahangMaks: number; bulatMaks: number };
  u: { bulatMin: number; rahangMaks: number };
  o: { bulatMin: number; rahangMin: number; rahangMaks: number };
  M: { celahMaks: number; rahangMaks: number; tekanMin: number; bulatMaks: number; lebarMaks: number };
}

/**
 * Ambang bawaan, ditentukan dari perilaku blendshape MediaPipe saat berbicara, bukan dari
 * pengukuran. Saat bicara biasa, gerakan mulut jauh lebih kecil daripada saat berpose:
 * jawOpen untuk "a" sekitar 0,3 sampai 0,6, mouthSmile untuk "i" sekitar 0,1 sampai 0,4,
 * dan mouthPucker/mouthFunnel untuk "u" dan "o" sekitar 0,3 sampai 0,8. Karena itu ambang
 * dibuat lebih longgar dari tebakan pertama.
 *
 * Batas antar-bentuk dibuat berbagi angka yang sama (misalnya bulatMaks "a" = bulatMin "o"),
 * sehingga satu bentuk bibir tidak pernah lolos sebagai dua bunyi; lihat cekTumpang().
 * Untuk wajah tertentu, setelOtomatis() menghitung ambang dari contoh bentuk orang itu.
 */
export const AMBANG_BAWAAN: Ambang = {
  // "a": rahang paling terbuka, bibir tidak membulat.
  a: { rahangMin: 0.3, bulatMaks: 0.25 },
  // "i": bibir melebar, rahang hampir tertutup, tidak membulat.
  i: { lebarMin: 0.15, rahangMaks: 0.3, bulatMaks: 0.15 },
  // "u": paling membulat, rahang hampir tertutup.
  u: { bulatMin: 0.35, rahangMaks: 0.12 },
  // "o": membulat dengan rahang terbuka sedang, di antara "u" dan "a".
  o: { bulatMin: 0.25, rahangMin: 0.12, rahangMaks: 0.45 },
  // Bibir rapat: celah hampir nol, tidak membulat (bukan "u"), tidak melebar (bukan "i").
  M: { celahMaks: 0.02, rahangMaks: 0.15, tekanMin: 0, bulatMaks: 0.25, lebarMaks: 0.15 },
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
      // Di dalam kata ("bu", "mi") bibir boleh mengatup sambil bersiap ke vokal berikutnya.
      if (!dalamKata && f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      if (!dalamKata && f.lebar >= t.lebarMaks) return kurang('rapatkan');
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
        dalamKata ? 1 : dekatMaks(f.lebar, ambang.M.lebarMaks),
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

// ------------------------------------------------- tumpang tindih dan penyetelan

const BENTUK_TUNGGAL: readonly Bunyi[] = ['a', 'i', 'u', 'o', 'M'];

/**
 * Pasangan bunyi yang bisa lolos bersamaan untuk bentuk bibir yang sama, dicari di
 * seluruh ruang angka. Kosong berarti ambangnya aman.
 */
export function cekTumpang(ambang: Ambang = AMBANG_BAWAAN): [Bunyi, Bunyi][] {
  const hasil = new Set<string>();
  const langkah = [0, 0.02, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.8];
  for (const rahang of langkah) {
    for (const bulat of langkah) {
      for (const lebar of langkah) {
        for (const celah of [0, 0.01, 0.02, 0.05, 0.1]) {
          const f: Fitur = { rahang, bulat, lebar, tekan: 0, celah };
          const lolos = BENTUK_TUNGGAL.filter((b) => nilaiBentuk(b, f, ambang).cocok);
          for (let x = 0; x < lolos.length; x++) {
            for (let y = x + 1; y < lolos.length; y++) hasil.add(`${lolos[x]}|${lolos[y]}`);
          }
        }
      }
    }
  }
  return [...hasil].map((pasangan) => pasangan.split('|') as [Bunyi, Bunyi]);
}

/** Nilai tengah (median) tiap angka dari sekumpulan frame. */
export function medianFitur(frame: readonly Fitur[]): Fitur {
  const tengah = (kunci: keyof Fitur) => {
    const urut = frame.map((f) => f[kunci]).sort((a, b) => a - b);
    const m = Math.floor(urut.length / 2);
    return urut.length % 2 ? urut[m]! : ((urut[m - 1] ?? 0) + (urut[m] ?? 0)) / 2;
  };
  return { rahang: tengah('rahang'), bulat: tengah('bulat'), lebar: tengah('lebar'), tekan: tengah('tekan'), celah: tengah('celah') };
}

export type HasilSetel = { ok: true; ambang: Ambang } | { ok: false; masalah: string[] };

/** Selisih terkecil antar-bentuk supaya bisa dibedakan dengan andal. */
const JARAK_MIN = 0.05;
const JARAK_MIN_CELAH = 0.008;

/**
 * Menghitung ambang dari contoh bentuk satu orang (median tiap bentuk, setelah kalibrasi
 * netral). Batas diletakkan di tengah antara bentuk yang harus dibedakan. Kalau ada dua
 * bentuk yang terlalu mirip, tidak ada yang diubah dan masalahnya dilaporkan, supaya
 * penguji bisa mengulang bentuk itu dengan lebih jelas.
 */
export function setelOtomatis(contoh: Record<Bunyi, Fitur>): HasilSetel {
  const { a, i, u, o, M } = contoh;
  const masalah: string[] = [];
  const syarat = (benar: boolean, pesan: string) => {
    if (!benar) masalah.push(pesan);
  };
  const tengah = (x: number, y: number) => (x + y) / 2;
  const maks = Math.max;
  const min = Math.min;

  // Tiap pasangan bentuk cukup dibedakan oleh SATU ciri; syarat lain tidak perlu.
  // a vs o dan a vs u: kebulatan. a vs i: rahang. o vs u: rahang. i vs lainnya: lebar.
  // Bibir rapat vs a/o: celah; vs u: kebulatan; vs i: lebar.
  syarat(a.rahang - maks(i.rahang, M.rahang) >= JARAK_MIN, '"a" belum cukup lebih terbuka daripada "i". Buka mulut lebih lebar saat "a".');
  syarat(o.rahang - u.rahang >= JARAK_MIN, '"o" dan "u" terlalu mirip. Buka rahang sedikit saat "o", rapatkan saat "u".');
  syarat(min(o.bulat, u.bulat) - maks(a.bulat, i.bulat, M.bulat) >= JARAK_MIN, '"o" dan "u" belum cukup membulat dibandingkan "a", "i", dan bibir rapat.');
  syarat(i.lebar - maks(a.lebar, o.lebar, u.lebar, M.lebar) >= JARAK_MIN, '"i" belum cukup melebar. Tarik bibir ke samping saat "i".');
  syarat(min(a.celah, o.celah) - M.celah >= JARAK_MIN_CELAH, 'Bibir belum benar-benar rapat saat "m". Rapatkan kedua bibir sepenuhnya.');
  if (masalah.length) return { ok: false, masalah };

  // Batas bersama: angka yang sama dipakai dua bentuk, jadi keduanya tidak bisa lolos bersamaan.
  const batasBulat = tengah(maks(a.bulat, i.bulat, M.bulat), min(o.bulat, u.bulat));
  const batasRahangUo = tengah(u.rahang, o.rahang);
  const batasRahangIa = tengah(maks(i.rahang, M.rahang), a.rahang);
  const batasLebar = tengah(maks(a.lebar, o.lebar, u.lebar, M.lebar), i.lebar);

  const ambang: Ambang = {
    a: { rahangMin: batasRahangIa, bulatMaks: batasBulat },
    i: { lebarMin: batasLebar, rahangMaks: batasRahangIa, bulatMaks: min(tengah(i.bulat, min(o.bulat, u.bulat)), batasBulat) },
    u: { bulatMin: maks(tengah(maks(a.bulat, i.bulat, M.bulat), u.bulat), batasBulat), rahangMaks: batasRahangUo },
    // Batas atas "o" longgar: "o" yang terbuka lebar tetap dibedakan dari "a" oleh kebulatan.
    o: { bulatMin: batasBulat, rahangMin: batasRahangUo, rahangMaks: maks(o.rahang + 0.2, a.rahang) },
    M: {
      celahMaks: tengah(M.celah, min(a.celah, o.celah)),
      rahangMaks: min(maks(M.rahang + 0.1, 0.1), batasRahangIa),
      tekanMin: 0,
      bulatMaks: batasBulat,
      lebarMaks: batasLebar,
    },
  };
  const tumpang = cekTumpang(ambang);
  if (tumpang.length) {
    return { ok: false, masalah: tumpang.map(([x, y]) => `"${x}" dan "${y}" masih bisa tertukar. Ulangi kedua bentuk dengan lebih jelas.`) };
  }
  return { ok: true, ambang };
}
