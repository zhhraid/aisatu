import { BENTUK_BIBIR, type Bunyi, type Fitur } from './tipe';

/**
 * Ambang aturan bentuk bibir. Semua angka kecuali celah adalah selisih blendshape
 * MediaPipe dari wajah netral anak (0 sampai 1).
 */
export interface Ambang {
  a: { rahangMin: number; bulatMaks: number };
  i: { lebarMin: number; rahangMaks: number; bulatMaks: number };
  u: { bulatMin: number; rahangMaks: number };
  o: { bulatMin: number; rahangMin: number; rahangMaks: number };
  M: {
    celahMaks: number; rahangMaks: number; tekanMin: number; bulatMaks: number; lebarMaks: number;
    gulungMaks: number;
  };
  e: { rahangMin: number; rahangMaks: number; bulatMaks: number };
  F: { gulungMin: number; rahangMaks: number; bulatMaks: number; lebarMaks: number };
  /** "h": mulut tidak tertutup; sisanya dinilai dari hembusan napas di mikrofon. */
  H: { celahMin: number };
  /** Desis (s, c, x, z, j): gigi hampir rapat, bibir sedikit terbuka; plus desis di mikrofon. */
  S: { rahangMaks: number; bulatMaks: number; celahMin: number };
  /** Huruf lidah (t, d, n, l, r, k, g, q): mulut sedikit terbuka; plus ada bunyi. */
  T: { celahMin: number; rahangMaks: number };
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
  i: { lebarMin: 0.15, rahangMaks: 0.12, bulatMaks: 0.15 },
  // "u": paling membulat, rahang hampir tertutup.
  u: { bulatMin: 0.35, rahangMaks: 0.12 },
  // "o": membulat dengan rahang terbuka sedang, di antara "u" dan "a".
  o: { bulatMin: 0.25, rahangMin: 0.12, rahangMaks: 0.45 },
  // Bibir rapat: celah hampir nol, tidak membulat (bukan "u"), tidak melebar (bukan "i").
  M: { celahMaks: 0.02, rahangMaks: 0.12, tekanMin: 0, bulatMaks: 0.25, lebarMaks: 0.15, gulungMaks: 0.2 },
  // "e": rahang terbuka sedang, di antara "i" (hampir tertutup) dan "a" (lebar), tidak membulat.
  e: { rahangMin: 0.12, rahangMaks: 0.3, bulatMaks: 0.25 },
  // "f/v": bibir bawah tergulung ke bawah gigi atas, rahang hampir tertutup.
  F: { gulungMin: 0.2, rahangMaks: 0.12, bulatMaks: 0.25, lebarMaks: 0.15 },
  H: { celahMin: 0.02 },
  // Dinilai sebagian: hanya posisi mulut yang terlihat, bukan lidah.
  S: { rahangMaks: 0.15, bulatMaks: 0.35, celahMin: 0.005 },
  T: { celahMin: 0.01, rahangMaks: 0.35 },
};

export type Petunjuk =
  | 'buka_lebar'
  | 'buka_sedikit'
  | 'tutup_sedikit'
  | 'jangan_bulatkan'
  | 'tarik_samping'
  | 'kerucutkan'
  | 'bulatkan'
  | 'rapatkan'
  | 'gigi_ke_bibir'
  | 'buka_mulut'
  | 'gigi_rapat';

export const TEKS_PETUNJUK: Record<Petunjuk, string> = {
  buka_lebar: 'Buka mulut lebih lebar',
  buka_sedikit: 'Buka mulut sedikit',
  tutup_sedikit: 'Jangan terlalu terbuka',
  jangan_bulatkan: 'Jangan bulatkan bibir',
  tarik_samping: 'Tarik bibir ke samping',
  kerucutkan: 'Kerucutkan bibir',
  bulatkan: 'Bulatkan bibir',
  rapatkan: 'Rapatkan bibir',
  gigi_ke_bibir: 'Tempelkan gigi atas ke bibir bawah',
  buka_mulut: 'Buka mulut sedikit',
  gigi_rapat: 'Rapatkan gigi, buka bibir sedikit',
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
      // rahangMaks eksklusif: angka yang sama adalah rahangMin "e".
      if (f.celah > t.celahMaks || f.rahang >= t.rahangMaks || f.tekan < t.tekanMin) {
        return kurang('rapatkan');
      }
      // Di dalam kata ("bu", "mi") bibir boleh mengatup sambil bersiap ke vokal berikutnya.
      if (!dalamKata && f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      if (!dalamKata && f.lebar >= t.lebarMaks) return kurang('rapatkan');
      if ((f.gulung ?? 0) >= t.gulungMaks) return kurang('rapatkan');
      return COCOK;
    }
    case 'e': {
      const t = ambang.e;
      if (f.rahang < t.rahangMin) return kurang('buka_sedikit');
      if (f.rahang >= t.rahangMaks) return kurang('tutup_sedikit');
      if (f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      return COCOK;
    }
    case 'F': {
      const t = ambang.F;
      if ((f.gulung ?? 0) < t.gulungMin) return kurang('gigi_ke_bibir');
      if (f.rahang >= t.rahangMaks) return kurang('tutup_sedikit');
      if (f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      if (f.lebar >= t.lebarMaks) return kurang('gigi_ke_bibir');
      return COCOK;
    }
    case 'H': {
      if (f.celah < ambang.H.celahMin) return kurang('buka_mulut');
      return COCOK;
    }
    case 'S': {
      const t = ambang.S;
      if (f.rahang >= t.rahangMaks) return kurang('gigi_rapat');
      if (f.celah < t.celahMin) return kurang('gigi_rapat');
      if (f.bulat >= t.bulatMaks) return kurang('jangan_bulatkan');
      return COCOK;
    }
    case 'T': {
      const t = ambang.T;
      if (f.celah < t.celahMin) return kurang('buka_mulut');
      if (f.rahang >= t.rahangMaks) return kurang('tutup_sedikit');
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
        dekatMaks(f.gulung ?? 0, ambang.M.gulungMaks),
      ];
      break;
    case 'e':
      bagian = [
        dekatMin(f.rahang, ambang.e.rahangMin),
        dekatMaks(f.rahang, ambang.e.rahangMaks),
        dekatMaks(f.bulat, ambang.e.bulatMaks),
      ];
      break;
    case 'F':
      bagian = [
        dekatMin(f.gulung ?? 0, ambang.F.gulungMin),
        dekatMaks(f.rahang, ambang.F.rahangMaks),
        dekatMaks(f.bulat, ambang.F.bulatMaks),
        dekatMaks(f.lebar, ambang.F.lebarMaks),
      ];
      break;
    case 'H':
      bagian = [dekatMin(f.celah, ambang.H.celahMin)];
      break;
    case 'S':
      bagian = [
        dekatMaks(f.rahang, ambang.S.rahangMaks),
        dekatMin(f.celah, ambang.S.celahMin),
        dekatMaks(f.bulat, ambang.S.bulatMaks),
      ];
      break;
    case 'T':
      bagian = [dekatMin(f.celah, ambang.T.celahMin), dekatMaks(f.rahang, ambang.T.rahangMaks)];
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

const BENTUK_HURUF: Record<string, Bunyi> = {
  a: 'a', i: 'i', u: 'u', e: 'e', o: 'o',
  m: 'M', b: 'M', p: 'M',
  f: 'F', v: 'F',
  w: 'u', y: 'i',
  h: 'H',
  s: 'S', c: 'S', x: 'S', z: 'S', j: 'S',
  t: 'T', d: 'T', n: 'T', l: 'T', r: 'T', k: 'T', g: 'T', q: 'T',
};

/**
 * Urutan bentuk yang dinilai dari sebuah kata. Dua bentuk sama yang berurutan digabung
 * ("ng" menjadi satu "T"). Sama dengan aturan di backend.
 */
export function urutanDariTeks(teks: string): Bunyi[] {
  const hasil: Bunyi[] = [];
  for (const huruf of teks.toLowerCase()) {
    const bentuk = BENTUK_HURUF[huruf];
    if (bentuk && hasil[hasil.length - 1] !== bentuk) hasil.push(bentuk);
  }
  return hasil;
}

// ------------------------------------------------- tumpang tindih dan penyetelan

/**
 * Pasangan bunyi yang bisa lolos bersamaan untuk bentuk bibir yang sama, dicari di
 * seluruh ruang angka. Kosong berarti ambangnya aman. "H" tidak ikut, karena dibedakan
 * dari hembusan napas, bukan dari bentuk bibir.
 */
export function cekTumpang(ambang: Ambang = AMBANG_BAWAAN): [Bunyi, Bunyi][] {
  const hasil = new Set<string>();
  const langkah = [0, 0.02, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.8];
  for (const rahang of langkah) {
    for (const bulat of langkah) {
      for (const lebar of langkah) {
        for (const celah of [0, 0.01, 0.02, 0.05, 0.1]) {
          for (const gulung of [-0.1, 0, 0.1, 0.2, 0.3, 0.5]) {
            const f: Fitur = { rahang, bulat, lebar, tekan: 0, celah, gulung };
            const lolos = BENTUK_BIBIR.filter((b) => nilaiBentuk(b, f, ambang).cocok);
            for (let x = 0; x < lolos.length; x++) {
              for (let y = x + 1; y < lolos.length; y++) hasil.add(`${lolos[x]}|${lolos[y]}`);
            }
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
    const urut = frame.map((f) => f[kunci] ?? 0).sort((a, b) => a - b);
    const m = Math.floor(urut.length / 2);
    return urut.length % 2 ? urut[m]! : ((urut[m - 1] ?? 0) + (urut[m] ?? 0)) / 2;
  };
  return {
    rahang: tengah('rahang'), bulat: tengah('bulat'), lebar: tengah('lebar'),
    tekan: tengah('tekan'), celah: tengah('celah'), gulung: tengah('gulung'),
  };
}

export type HasilSetel = { ok: true; ambang: Ambang } | { ok: false; masalah: string[] };

/** Selisih terkecil antar-bentuk supaya bisa dibedakan dengan andal. */
const JARAK_MIN = 0.05;
const JARAK_MIN_CELAH = 0.008;

/**
 * Menghitung ambang dari contoh bentuk satu orang (median tiap bentuk bibir, setelah
 * kalibrasi netral). Batas diletakkan di tengah antara bentuk yang harus dibedakan. Kalau
 * ada dua bentuk yang terlalu mirip, tidak ada yang diubah dan masalahnya dilaporkan,
 * supaya penguji bisa mengulang bentuk itu dengan lebih jelas.
 */
export function setelOtomatis(contoh: Record<Exclude<Bunyi, 'H' | 'S' | 'T'>, Fitur>): HasilSetel {
  const { a, i, u, o, M, e, F } = contoh;
  const g = (f: Fitur) => f.gulung ?? 0;
  const masalah: string[] = [];
  const syarat = (benar: boolean, pesan: string) => {
    if (!benar) masalah.push(pesan);
  };
  const tengah = (x: number, y: number) => (x + y) / 2;
  const maks = Math.max;
  const min = Math.min;
  const rata = [a, i, M, e, F]; // bentuk yang tidak membulat

  // Tiap pasangan bentuk cukup dibedakan oleh SATU ciri:
  // - membulat (u, o) vs tidak (a, i, e, rapat, f): kebulatan;
  // - di antara yang tidak membulat: rahang (i, rapat, f < e < a);
  // - di antara yang membulat: rahang (u < o);
  // - i vs rapat vs f (sama-sama rahang tertutup): lebar dan gulungan bibir bawah;
  // - rapat vs a/o/e: celah.
  syarat(min(o.bulat, u.bulat) - maks(...rata.map((f) => f.bulat)) >= JARAK_MIN, '"o" dan "u" belum cukup membulat dibandingkan bentuk lain.');
  syarat(o.rahang - u.rahang >= JARAK_MIN, '"o" dan "u" terlalu mirip. Buka rahang sedikit saat "o", rapatkan saat "u".');
  syarat(e.rahang - maks(i.rahang, M.rahang, F.rahang) >= JARAK_MIN, '"e" belum cukup lebih terbuka daripada "i". Buka mulut sedikit saat "e".');
  syarat(a.rahang - e.rahang >= JARAK_MIN, '"a" belum cukup lebih terbuka daripada "e". Buka mulut lebih lebar saat "a".');
  syarat(i.lebar - maks(M.lebar, F.lebar) >= JARAK_MIN, '"i" belum cukup melebar. Tarik bibir ke samping saat "i".');
  syarat(g(F) - maks(g(a), g(i), g(u), g(o), g(M), g(e)) >= JARAK_MIN, '"f" belum terlihat berbeda. Gigit sedikit bibir bawah dengan gigi atas saat "f".');
  syarat(min(a.celah, o.celah, e.celah) - M.celah >= JARAK_MIN_CELAH, 'Bibir belum benar-benar rapat saat "m". Rapatkan kedua bibir sepenuhnya.');
  if (masalah.length) return { ok: false, masalah };

  // Batas bersama: angka yang sama dipakai dua bentuk, jadi keduanya tidak bisa lolos bersamaan.
  const batasBulat = tengah(maks(...rata.map((f) => f.bulat)), min(o.bulat, u.bulat));
  const batasRahangUo = tengah(u.rahang, o.rahang);
  const batasRahangTutup = tengah(maks(i.rahang, M.rahang, F.rahang), e.rahang);
  const batasRahangEa = tengah(e.rahang, a.rahang);
  const batasLebar = tengah(maks(M.lebar, F.lebar), i.lebar);
  const batasGulung = tengah(maks(g(a), g(i), g(u), g(o), g(M), g(e)), g(F));

  const ambang: Ambang = {
    a: { rahangMin: batasRahangEa, bulatMaks: batasBulat },
    i: { lebarMin: batasLebar, rahangMaks: batasRahangTutup, bulatMaks: min(tengah(i.bulat, min(o.bulat, u.bulat)), batasBulat) },
    u: { bulatMin: maks(tengah(maks(...rata.map((f) => f.bulat)), u.bulat), batasBulat), rahangMaks: batasRahangUo },
    // Batas atas "o" longgar: "o" yang terbuka lebar tetap dibedakan dari "a" oleh kebulatan.
    o: { bulatMin: batasBulat, rahangMin: batasRahangUo, rahangMaks: maks(o.rahang + 0.2, a.rahang) },
    M: {
      celahMaks: tengah(M.celah, min(a.celah, o.celah, e.celah)),
      rahangMaks: min(maks(M.rahang + 0.1, 0.1), batasRahangTutup),
      tekanMin: 0,
      bulatMaks: batasBulat,
      lebarMaks: batasLebar,
      gulungMaks: batasGulung,
    },
    e: { rahangMin: batasRahangTutup, rahangMaks: batasRahangEa, bulatMaks: batasBulat },
    F: { gulungMin: batasGulung, rahangMaks: batasRahangTutup, bulatMaks: batasBulat, lebarMaks: batasLebar },
    H: { ...AMBANG_BAWAAN.H },
    S: { ...AMBANG_BAWAAN.S },
    T: { ...AMBANG_BAWAAN.T },
  };
  const tumpang = cekTumpang(ambang);
  if (tumpang.length) {
    return { ok: false, masalah: tumpang.map(([x, y]) => `"${x}" dan "${y}" masih bisa tertukar. Ulangi kedua bentuk dengan lebih jelas.`) };
  }
  return { ok: true, ambang };
}
