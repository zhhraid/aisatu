import { DINILAI_SEBAGIAN, type Bunyi } from './tipe';

/**
 * Bentuk bibir contoh untuk huruf a sampai z, sebagai koordinat titik bibir
 * MediaPipe Face Landmarker (indeks yang sama dengan FACE_LANDMARKS_LIPS).
 * Bentuknya dibangkitkan dari beberapa parameter, bukan direkam dari wajah,
 * jadi bisa digambar di panel Tutorial dengan garis yang sama seperti titik
 * bibir anak di kamera.
 *
 * Koordinat dinormalkan ke kotak 1 x 1 dengan pusat mulut di (0,5; 0,5),
 * sumbu y ke bawah seperti koordinat gambar.
 */

// Urutan titik dari sudut kiri ke sudut kanan gambar, sesuai sambungan MediaPipe.
export const LUAR_BAWAH = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291] as const;
export const LUAR_ATAS = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291] as const;
export const DALAM_BAWAH = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308] as const;
export const DALAM_ATAS = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308] as const;

/** Semua 40 indeks titik bibir MediaPipe yang dipakai, tanpa duplikat. */
export const INDEKS_BIBIR: readonly number[] = [
  ...new Set([...LUAR_BAWAH, ...LUAR_ATAS, ...DALAM_BAWAH, ...DALAM_ATAS]),
];

export type BentukTutorial =
  | 'netral'
  | 'a'
  | 'i'
  | 'u'
  | 'e'
  | 'o'
  | 'katup'
  | 'gigi_bibir'
  | 'lidah'
  | 'hembusan'
  | 'desis';

interface ParamBentuk {
  /** Setengah lebar mulut, dari pusat ke sudut. */
  lebar: number;
  /** Tinggi bukaan di tengah mulut (jarak bibir dalam atas ke bawah). */
  buka: number;
  /** 0 = sudut mulut tajam, 1 = mulut membulat. */
  bulat: number;
  /** Tebal bibir atas dan bawah. */
  tebalAtas: number;
  tebalBawah: number;
  /** Bibir bawah naik menyentuh gigi atas (f, v). */
  bibirBawahNaik?: boolean;
}

// Angka disamakan arahnya dengan aturan di aturan.ts: "a" rahang paling terbuka,
// "i" paling lebar, "u" paling sempit dan bulat, "o" bulat dengan bukaan sedang,
// bibir mengatup tanpa bukaan.
const PARAM: Record<BentukTutorial, ParamBentuk> = {
  netral: { lebar: 0.3, buka: 0, bulat: 0, tebalAtas: 0.07, tebalBawah: 0.09 },
  a: { lebar: 0.29, buka: 0.3, bulat: 0.15, tebalAtas: 0.06, tebalBawah: 0.07 },
  i: { lebar: 0.38, buka: 0.05, bulat: 0, tebalAtas: 0.05, tebalBawah: 0.06 },
  u: { lebar: 0.15, buka: 0.07, bulat: 1, tebalAtas: 0.09, tebalBawah: 0.1 },
  e: { lebar: 0.34, buka: 0.13, bulat: 0.05, tebalAtas: 0.055, tebalBawah: 0.065 },
  o: { lebar: 0.21, buka: 0.19, bulat: 0.85, tebalAtas: 0.08, tebalBawah: 0.09 },
  katup: { lebar: 0.3, buka: 0, bulat: 0, tebalAtas: 0.05, tebalBawah: 0.06 },
  gigi_bibir: {
    lebar: 0.31, buka: 0.04, bulat: 0, tebalAtas: 0.065, tebalBawah: 0.06, bibirBawahNaik: true,
  },
  lidah: { lebar: 0.31, buka: 0.08, bulat: 0.05, tebalAtas: 0.065, tebalBawah: 0.08 },
  hembusan: { lebar: 0.3, buka: 0.15, bulat: 0.1, tebalAtas: 0.06, tebalBawah: 0.075 },
  desis: { lebar: 0.33, buka: 0.045, bulat: 0, tebalAtas: 0.055, tebalBawah: 0.065 },
};

export interface HurufTutorial {
  huruf: string;
  bentuk: BentukTutorial;
  /** Bentuk yang dinilai kamera untuk huruf ini, atau null kalau tidak bisa dinilai. */
  dinilai: Bunyi | null;
  /** True kalau hanya dinilai sebagian (posisi mulut dan suara, bukan lidah). */
  sebagian: boolean;
  /** Petunjuk singkat untuk anak dan pendamping. */
  petunjuk: string;
}

const PETUNJUK: Record<BentukTutorial, string> = {
  netral: 'Bibir santai dan tertutup.',
  a: 'Buka mulut lebar.',
  i: 'Tarik bibir ke samping, gigi hampir bertemu.',
  u: 'Kerucutkan bibir ke depan.',
  e: 'Buka mulut sedikit, bibir agak ke samping.',
  o: 'Bulatkan bibir, buka sedikit.',
  katup: 'Rapatkan kedua bibir, lalu buka.',
  gigi_bibir: 'Gigi atas menyentuh bibir bawah.',
  lidah: 'Buka mulut sedikit; bunyi ini dibentuk lidah. Perhatikan posisi lidah guru.',
  hembusan: 'Buka mulut dan hembuskan napas. Coba dengan tisu di depan mulut.',
  desis: 'Rapatkan gigi, buka bibir sedikit, lalu desiskan udara (sss).',
};

const BENTUK_HURUF: Record<string, BentukTutorial> = {
  a: 'a', i: 'i', u: 'u', e: 'e', o: 'o',
  m: 'katup', b: 'katup', p: 'katup',
  f: 'gigi_bibir', v: 'gigi_bibir',
  w: 'u', y: 'i',
  h: 'hembusan',
  s: 'desis', c: 'desis', x: 'desis', z: 'desis', j: 'desis',
};

// Bentuk yang punya aturan di aturan.ts. "h" dinilai dari hembusan napas; desis dan
// huruf lidah dinilai sebagian (posisi mulut dan suara, bukan lidah).
const DINILAI: Partial<Record<BentukTutorial, Bunyi>> = {
  a: 'a', i: 'i', u: 'u', e: 'e', o: 'o', katup: 'M', gigi_bibir: 'F', hembusan: 'H',
  desis: 'S', lidah: 'T',
};

/** Data tutorial untuk satu huruf. Huruf di luar a-z memakai bentuk netral. */
export function hurufTutorial(huruf: string): HurufTutorial {
  const h = huruf.toLowerCase();
  const bentuk: BentukTutorial = BENTUK_HURUF[h] ?? (/^[a-z]$/.test(h) ? 'lidah' : 'netral');
  // w dan y memakai bentuk u dan i, dan dinilai sebagai bentuk itu. Selain a-z: tidak dinilai.
  const dinilai = /^[a-z]$/.test(h) ? (DINILAI[bentuk] ?? null) : null;
  const sebagian = dinilai !== null && DINILAI_SEBAGIAN.includes(dinilai);
  return { huruf: h, bentuk, dinilai, sebagian, petunjuk: PETUNJUK[bentuk] };
}

export const ABJAD: readonly HurufTutorial[] = 'abcdefghijklmnopqrstuvwxyz'
  .split('')
  .map(hurufTutorial);

export interface Titik2D {
  x: number;
  y: number;
}

/** Bentuk lengkung: sudut tajam untuk mulut lebar, makin bulat makin seperti elips. */
function lengkung(t: number, bulat: number): number {
  const s = Math.sin(Math.PI * t);
  return Math.pow(s, 1 - 0.55 * bulat);
}

/** Koordinat 40 titik bibir untuk satu bentuk, dikunci dengan indeks MediaPipe. */
export function koordinatBentuk(bentuk: BentukTutorial): Record<number, Titik2D> {
  const p = PARAM[bentuk];
  const cx = 0.5;
  const cy = 0.5;
  // Sudut dalam sedikit lebih ke tengah dari sudut luar.
  const lebarDalam = p.lebar * (p.bulat > 0.5 ? 0.7 : 0.85);
  const naik = p.bibirBawahNaik ? 0.03 : 0;
  const hasil: Record<number, Titik2D> = {};

  const isi = (indeks: readonly number[], lebar: number, tinggi: (t: number) => number) => {
    indeks.forEach((idx, i) => {
      const t = i / (indeks.length - 1);
      hasil[idx] = { x: cx - lebar + 2 * lebar * t, y: cy + tinggi(t) };
    });
  };

  const separuh = p.buka / 2;
  isi(DALAM_ATAS, lebarDalam, (t) => -separuh * lengkung(t, p.bulat) - naik);
  isi(DALAM_BAWAH, lebarDalam, (t) => separuh * lengkung(t, p.bulat) - naik);
  isi(LUAR_ATAS, p.lebar, (t) => {
    const busur = -(separuh + p.tebalAtas) * lengkung(t, p.bulat) - naik;
    // Lekuk busur di tengah bibir atas (titik 0) supaya terlihat seperti bibir.
    const lekuk = 0.018 * Math.exp(-Math.pow((t - 0.5) / 0.07, 2));
    return busur + lekuk;
  });
  // Untuk f/v bibir bawah naik di tengah; sudut mulut tetap di tempatnya.
  isi(LUAR_BAWAH, p.lebar, (t) => (separuh + p.tebalBawah) * lengkung(t, p.bulat) - naik - naik * lengkung(t, 0));
  return hasil;
}

/** Koordinat bibir contoh untuk satu huruf. */
export function koordinatHuruf(huruf: string): Record<number, Titik2D> {
  return koordinatBentuk(hurufTutorial(huruf).bentuk);
}

/** Semua huruf a-z beserta koordinatnya, misalnya untuk disimpan sebagai JSON. */
export function semuaKoordinat(): Record<string, HurufTutorial & { titik: Record<number, Titik2D> }> {
  return Object.fromEntries(
    ABJAD.map((h) => [h.huruf, { ...h, titik: koordinatBentuk(h.bentuk) }]),
  );
}

export interface OpsiGambar {
  warnaBibir?: string;
  warnaMulut?: string;
  warnaGigi?: string;
  /** Hanya garis, tanpa isian (untuk ditumpuk di atas video). */
  garisSaja?: boolean;
}

/** Menggambar bentuk bibir contoh, mengisi kanvas dengan sedikit tepi. */
export function gambarBibir(
  ctx: CanvasRenderingContext2D,
  titik: Record<number, Titik2D>,
  opsi: OpsiGambar = {},
): void {
  const { width: l, height: t } = ctx.canvas;
  const skala = Math.min(l, t) * 1.3;
  const ke = (idx: number): [number, number] => {
    const p = titik[idx] ?? { x: 0.5, y: 0.5 };
    return [l / 2 + (p.x - 0.5) * skala, t / 2 + (p.y - 0.5) * skala];
  };
  // Garis dihaluskan lewat titik tengah tiap pasangan titik, supaya tidak patah-patah.
  const jalur = (atas: readonly number[], bawah: readonly number[]) => {
    const urut = [...atas, ...[...bawah].reverse().slice(1, -1)].map(ke);
    const tengah = (a: [number, number], b: [number, number]): [number, number] => [
      (a[0] + b[0]) / 2,
      (a[1] + b[1]) / 2,
    ];
    ctx.beginPath();
    ctx.moveTo(...tengah(urut[urut.length - 1]!, urut[0]!));
    urut.forEach((titikIni, i) => {
      ctx.quadraticCurveTo(...titikIni, ...tengah(titikIni, urut[(i + 1) % urut.length]!));
    });
    ctx.closePath();
  };

  ctx.clearRect(0, 0, l, t);
  ctx.lineJoin = 'round';
  ctx.lineWidth = Math.max(2, skala / 120);
  const warnaBibir = opsi.warnaBibir ?? '#d9707a';

  jalur(LUAR_ATAS, LUAR_BAWAH);
  if (opsi.garisSaja) {
    ctx.strokeStyle = warnaBibir;
    ctx.stroke();
  } else {
    ctx.fillStyle = warnaBibir;
    ctx.fill();
  }

  jalur(DALAM_ATAS, DALAM_BAWAH);
  if (opsi.garisSaja) {
    ctx.stroke();
    return;
  }
  ctx.fillStyle = opsi.warnaMulut ?? '#5a1f2a';
  ctx.fill();

  // Gigi atas terlihat saat mulut terbuka, dan untuk f/v.
  const [, yAtas] = ke(13);
  const [, yBawah] = ke(14);
  if (yBawah - yAtas > 2) {
    ctx.save();
    jalur(DALAM_ATAS, DALAM_BAWAH);
    ctx.clip();
    const [xKiri] = ke(78);
    const [xKanan] = ke(308);
    ctx.fillStyle = opsi.warnaGigi ?? '#fbf7f0';
    ctx.fillRect(xKiri, yAtas - 2, xKanan - xKiri, Math.max(4, (yBawah - yAtas) * 0.35));
    ctx.restore();
  }
}
