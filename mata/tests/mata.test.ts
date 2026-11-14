import { describe, expect, it } from 'vitest';
import { AMBANG_BAWAAN, kemiripan, nilaiBentuk, urutanDariTeks } from '../src/aturan';
import { ambilBlendshape, celahBibir, hitungFitur, posisiWajah } from '../src/fitur';
import { Kalibrasi } from '../src/kalibrasi';
import { hitungBintang, Percobaan, type FramePercobaan } from '../src/percobaan';
import { hitungRms, PenentuSuara } from '../src/suara';
import type { Bunyi, Fitur, Titik } from '../src/tipe';

const DIAM: Fitur = { rahang: 0, bulat: 0, lebar: 0, tekan: 0, celah: 0.005 };
// Bentuk contoh yang jelas memenuhi tiap aturan bawaan.
const BENTUK: Record<Bunyi, Fitur> = {
  a: { rahang: 0.6, bulat: 0.05, lebar: 0.1, tekan: 0, celah: 0.18 },
  i: { rahang: 0.1, bulat: 0.02, lebar: 0.45, tekan: 0, celah: 0.04 },
  u: { rahang: 0.1, bulat: 0.6, lebar: 0, tekan: 0, celah: 0.03 },
  o: { rahang: 0.35, bulat: 0.5, lebar: 0, tekan: 0, celah: 0.1 },
  M: { rahang: 0.02, bulat: 0.05, lebar: 0, tekan: 0.1, celah: 0.004 },
};

describe('aturan bentuk bibir', () => {
  it('tiap bentuk contoh hanya cocok dengan bunyinya sendiri', () => {
    for (const bentuk of ['a', 'i', 'u', 'o'] as Bunyi[]) {
      for (const target of ['a', 'i', 'u', 'o', 'M'] as Bunyi[]) {
        expect(nilaiBentuk(target, BENTUK[bentuk]).cocok, `${bentuk} dinilai sebagai ${target}`).toBe(
          bentuk === target,
        );
      }
    }
  });

  it('memberi petunjuk dari syarat pertama yang belum terpenuhi', () => {
    expect(nilaiBentuk('a', DIAM).petunjuk).toBe('buka_lebar');
    expect(nilaiBentuk('a', BENTUK.o).petunjuk).toBe('buka_lebar');
    expect(nilaiBentuk('a', { ...BENTUK.a, bulat: 0.5 }).petunjuk).toBe('jangan_bulatkan');
    expect(nilaiBentuk('i', DIAM).petunjuk).toBe('tarik_samping');
    expect(nilaiBentuk('i', BENTUK.a).petunjuk).toBe('tutup_sedikit');
    expect(nilaiBentuk('u', DIAM).petunjuk).toBe('kerucutkan');
    expect(nilaiBentuk('o', BENTUK.u).petunjuk).toBe('buka_sedikit');
    expect(nilaiBentuk('o', DIAM).petunjuk).toBe('bulatkan');
    expect(nilaiBentuk('M', BENTUK.a).petunjuk).toBe('rapatkan');
  });

  it('bibir diam yang rapat cocok dengan M, dan bisa diperketat lewat tekanMin', () => {
    expect(nilaiBentuk('M', DIAM).cocok).toBe(true);
    const ketat = { ...AMBANG_BAWAAN, M: { ...AMBANG_BAWAAN.M, tekanMin: 0.2 } };
    expect(nilaiBentuk('M', DIAM, ketat).cocok).toBe(false);
  });

  it('bibir yang mengerucut rapat adalah "u", bukan mengatup', () => {
    // Saat mengucap "u" celah bibir bisa sekecil bibir yang rapat.
    const uRapat: Fitur = { rahang: 0.05, bulat: 0.6, lebar: 0, tekan: 0.1, celah: 0.01 };
    expect(nilaiBentuk('u', uRapat).cocok).toBe(true);
    expect(nilaiBentuk('M', uRapat)).toEqual({ cocok: false, petunjuk: 'jangan_bulatkan' });
    // Di dalam kata ("bu", "mo") bibir boleh mengatup sambil membulat.
    expect(nilaiBentuk('M', uRapat, AMBANG_BAWAAN, true).cocok).toBe(true);
  });

  it('urutan bentuk dari kata sama dengan aturan backend', () => {
    expect(urutanDariTeks('bola')).toEqual(['M', 'o', 'a']);
    expect(urutanDariTeks('mama')).toEqual(['M', 'a', 'M', 'a']);
    expect(urutanDariTeks('buku')).toEqual(['M', 'u']);
    expect(urutanDariTeks('ibu')).toEqual(['i', 'M', 'u']);
    expect(urutanDariTeks('Susu')).toEqual(['u']);
  });
});

describe('fitur', () => {
  it('menghitung selisih dari wajah netral', () => {
    const netral = { jawOpen: 0.1, mouthPucker: 0.2, mouthSmileLeft: 0.3, mouthSmileRight: 0.1 };
    const kini = {
      jawOpen: 0.6, mouthPucker: 0.25, mouthFunnel: 0.4,
      mouthSmileLeft: 0.5, mouthSmileRight: 0.5, mouthPressLeft: 0.2, mouthPressRight: 0.4,
    };
    const f = hitungFitur(kini, netral, 0.12);
    expect(f.rahang).toBeCloseTo(0.5);
    expect(f.bulat).toBeCloseTo(0.4); // funnel lebih besar dari selisih pucker
    expect(f.lebar).toBeCloseTo(0.3); // rata-rata (0,2 + 0,4)
    expect(f.tekan).toBeCloseTo(0.3);
    expect(f.celah).toBe(0.12);
  });

  it('wajah netral sendiri menghasilkan nol', () => {
    const netral = { jawOpen: 0.15, mouthPucker: 0.3, mouthSmileLeft: 0.2, mouthSmileRight: 0.2 };
    const f = hitungFitur(netral, netral, 0);
    expect([f.rahang, f.bulat, f.lebar, f.tekan]).toEqual([0, 0, 0, 0]);
  });

  it('hanya mengambil blendshape mulut', () => {
    const hasil = ambilBlendshape([
      { categoryName: 'jawOpen', score: 0.5 },
      { categoryName: 'browDownLeft', score: 0.9 },
      { categoryName: 'mouthPucker', score: 0.1 },
    ]);
    expect(hasil).toEqual({ jawOpen: 0.5, mouthPucker: 0.1 });
  });

  function wajah(ubah: Record<number, Titik> = {}): Titik[] {
    const titik: Titik[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
    Object.assign(titik, {
      10: { x: 0.5, y: 0.2 }, 152: { x: 0.5, y: 0.8 }, // dahi dan dagu
      1: { x: 0.5, y: 0.5 }, 234: { x: 0.3, y: 0.5 }, 454: { x: 0.7, y: 0.5 }, // hidung dan tepi
      13: { x: 0.5, y: 0.62 }, 14: { x: 0.5, y: 0.62 }, // bibir rapat
      ...ubah,
    });
    return titik;
  }

  it('celah bibir dibagi tinggi wajah dan tidak terpengaruh rasio gambar', () => {
    expect(celahBibir(wajah(), 640, 480)).toBe(0);
    const terbuka = wajah({ 14: { x: 0.5, y: 0.74 } });
    expect(celahBibir(terbuka, 640, 480)).toBeCloseTo(0.2);
    expect(celahBibir(terbuka, 480, 640)).toBeCloseTo(0.2);
  });

  it('menandai wajah yang terlalu jauh atau miring', () => {
    expect(posisiWajah(wajah(), 640, 480)).toBe('ok');
    const jauh = wajah({ 10: { x: 0.5, y: 0.45 }, 152: { x: 0.5, y: 0.55 } });
    expect(posisiWajah(jauh, 640, 480)).toBe('terlalu_jauh');
    const miring = wajah({ 1: { x: 0.34, y: 0.5 } });
    expect(posisiWajah(miring, 640, 480)).toBe('miring');
  });
});

describe('kalibrasi', () => {
  function jalankan(nilai: (i: number) => number | null, jumlah = 41): Kalibrasi {
    const k = new Kalibrasi();
    for (let i = 0; i < jumlah; i++) {
      const v = nilai(i);
      k.tambah(i * 50, v === null ? null : { jawOpen: v, mouthPucker: 0.2 });
    }
    return k;
  }

  it('merata-ratakan wajah netral selama dua detik', () => {
    const k = jalankan((i) => (i % 2 ? 0.1 : 0.12));
    expect(k.selesai()).toBe(true);
    const hasil = k.hasil();
    expect(hasil.ok && hasil.netral['jawOpen']).toBeCloseTo(0.11, 2);
    expect(hasil.ok && hasil.netral['mouthPucker']).toBeCloseTo(0.2);
  });

  it('belum selesai sebelum dua detik', () => {
    expect(jalankan(() => 0.1, 20).selesai()).toBe(false);
  });

  it('menolak kalau wajah jarang terlihat, banyak bergerak, atau mulut terbuka', () => {
    expect(jalankan((i) => (i < 5 ? 0.1 : null)).hasil()).toEqual({ ok: false, alasan: 'wajah_tidak_terlihat' });
    expect(jalankan((i) => (i % 2 ? 0.05 : 0.5)).hasil()).toEqual({ ok: false, alasan: 'banyak_bergerak' });
    expect(jalankan(() => 0.5).hasil()).toEqual({ ok: false, alasan: 'mulut_terbuka' });
  });
});

describe('suara', () => {
  it('menghitung RMS', () => {
    expect(hitungRms(new Float32Array([0.5, -0.5, 0.5, -0.5]))).toBeCloseTo(0.5);
    expect(hitungRms(new Float32Array())).toBe(0);
  });

  it('ambang mengikuti kebisingan ruangan dan suara ditahan sebentar', () => {
    const p = new PenentuSuara();
    expect(p.ambang).toBe(0.015); // ruangan sunyi: pakai ambang terendah
    p.aturKebisingan(0.02);
    expect(p.ambang).toBeCloseTo(0.05);
    expect(p.perbarui(0.04, 0)).toBe(false); // di bawah ambang
    expect(p.perbarui(0.08, 100)).toBe(true);
    expect(p.perbarui(0.01, 200)).toBe(true); // masih ditahan
    expect(p.perbarui(0.01, 300)).toBe(false);
  });
});

describe('percobaan', () => {
  /** Membuat frame tiap 50 ms dari daftar [fitur, suara, jumlah frame]. */
  function* aliran(bagian: [Fitur | null, boolean, number][]): Generator<FramePercobaan> {
    let t = 0;
    for (const [fitur, suara, jumlah] of bagian) {
      for (let i = 0; i < jumlah; i++) {
        yield { t, fitur, suara };
        t += 50;
      }
    }
  }

  function jalankan(urutan: Bunyi[], bagian: [Fitur | null, boolean, number][], opsi = {}) {
    const p = new Percobaan(urutan, AMBANG_BAWAAN, opsi);
    let terakhir = null;
    for (const frame of aliran(bagian)) {
      terakhir = p.proses(frame);
      if (p.hasil()) break;
    }
    return { hasil: p.hasil(), keadaan: terakhir! };
  }

  it('bunyi tunggal berhasil kalau bentuk dan suara ditahan 0,7 detik', () => {
    const { hasil } = jalankan(['a'], [[DIAM, false, 10], [BENTUK.a, true, 20]]);
    expect(hasil).toMatchObject({ berhasil: true, langkah_tercapai: 1 });
    expect(hasil!.durasi_ms).toBeGreaterThanOrEqual(1150);
    expect(hasil!.durasi_ms).toBeLessThan(1300);
  });

  it('bentuk benar tanpa suara tidak berhasil dan petunjuknya minta bersuara', () => {
    const { hasil, keadaan } = jalankan(['a'], [[BENTUK.a, false, 30]]);
    expect(hasil).toBeNull();
    expect(keadaan).toMatchObject({ cocok: true, suara: false, petunjuk: 'bersuara', progres: 0 });
  });

  it('suara tanpa bentuk yang benar tidak berhasil', () => {
    const { hasil, keadaan } = jalankan(['a'], [[BENTUK.o, true, 30]]);
    expect(hasil).toBeNull();
    expect(keadaan.petunjuk).toBe('buka_lebar');
  });

  it('gagal setelah batas waktu, dengan langkah tempat anak macet', () => {
    const { hasil } = jalankan(['a'], [[DIAM, true, 200]]);
    expect(hasil).toMatchObject({ berhasil: false, langkah_tercapai: 0 });
    expect(hasil!.durasi_ms).toBe(6000);
  });

  it('lepas sebentar tidak mengulang hitungan, lepas lama mengulang', () => {
    const sebentar = jalankan(['a'], [[BENTUK.a, true, 8], [DIAM, true, 2], [BENTUK.a, true, 8]]);
    expect(sebentar.hasil?.berhasil).toBe(true);
    const lama = jalankan(['a'], [[BENTUK.a, true, 8], [DIAM, true, 5], [BENTUK.a, true, 8]]);
    expect(lama.hasil).toBeNull();
  });

  it('wajah hilang menjeda waktu dan tidak dihitung gagal', () => {
    const { hasil, keadaan } = jalankan(['a'], [[null, false, 300]]);
    expect(hasil).toBeNull();
    expect(keadaan).toMatchObject({ status: 'jeda', sisaMs: 6000 });
  });

  it('kata dinilai sebagai urutan bentuk, bibir mengatup tidak perlu bersuara', () => {
    const { hasil } = jalankan(urutanDariTeks('bola'), [
      [BENTUK.M, false, 4],
      [BENTUK.o, true, 5],
      [BENTUK.a, true, 5],
    ]);
    expect(hasil).toMatchObject({ berhasil: true, langkah_tercapai: 3 });
  });

  it('kata yang urutannya salah gagal di langkah yang macet', () => {
    // Anak mengucapkan "ba" lalu berhenti: M dan o diminta, tapi yang muncul M lalu a.
    const { hasil } = jalankan(urutanDariTeks('bola'), [[BENTUK.M, false, 4], [BENTUK.a, true, 200]]);
    expect(hasil).toMatchObject({ berhasil: false, langkah_tercapai: 1 });
  });

  it('pada "bu" bibir boleh mengatup sambil sudah membulat', () => {
    const katupBulat: Fitur = { rahang: 0.03, bulat: 0.5, lebar: 0, tekan: 0.1, celah: 0.005 };
    const { hasil } = jalankan(urutanDariTeks('bu'), [[katupBulat, false, 4], [BENTUK.u, true, 6]]);
    expect(hasil).toMatchObject({ berhasil: true, langkah_tercapai: 2 });
    // Sebagai bunyi tunggal "m", bentuk yang sama tidak lolos.
    expect(jalankan(['M'], [[katupBulat, true, 30]]).hasil).toBeNull();
  });

  it('vokal di dalam kata tetap perlu suara', () => {
    const { hasil } = jalankan(urutanDariTeks('bola'), [
      [BENTUK.M, false, 4],
      [BENTUK.o, false, 10],
      [BENTUK.a, false, 200],
    ]);
    expect(hasil).toMatchObject({ berhasil: false, langkah_tercapai: 1 });
  });

  it('tanpaSuara mengabaikan syarat suara', () => {
    const { hasil } = jalankan(['u'], [[BENTUK.u, false, 20]], { tanpaSuara: true });
    expect(hasil?.berhasil).toBe(true);
  });

  it('progres naik per langkah dan urutan kosong ditolak', () => {
    const p = new Percobaan(['M', 'a'], AMBANG_BAWAAN);
    p.proses({ t: 0, fitur: BENTUK.M, suara: false });
    const k = p.proses({ t: 50, fitur: BENTUK.M, suara: false });
    expect(k).toMatchObject({ langkah: 1, target: 'a', jumlahLangkah: 2, progres: 0.5 });
    expect(() => new Percobaan([])).toThrow();
  });
});

describe('kemiripan dan bintang', () => {
  it('100% hanya kalau aturannya lolos, dan bentuk yang lebih dekat bernilai lebih tinggi', () => {
    expect(kemiripan('a', BENTUK.a)).toBe(1);
    const setengahBuka: Fitur = { ...DIAM, rahang: 0.25 };
    const hampir: Fitur = { ...DIAM, rahang: 0.4 };
    expect(kemiripan('a', DIAM)).toBeLessThan(kemiripan('a', setengahBuka));
    expect(kemiripan('a', setengahBuka)).toBeLessThan(kemiripan('a', hampir));
    expect(kemiripan('a', hampir)).toBeLessThanOrEqual(0.95);
    for (const b of ['a', 'i', 'u', 'o', 'M'] as Bunyi[]) {
      for (const f of [DIAM, ...Object.values(BENTUK)]) {
        const k = kemiripan(b, f);
        expect(k).toBeGreaterThanOrEqual(0);
        expect(k === 1).toBe(nilaiBentuk(b, f).cocok);
      }
    }
  });

  it('bentuk lain jauh dari target', () => {
    expect(kemiripan('u', BENTUK.a)).toBeLessThan(0.5);
    expect(kemiripan('M', BENTUK.a)).toBeLessThan(0.5);
  });

  it('bintang: berhasil dan mirip 3, berhasil 2, belum berhasil tetap 1', () => {
    expect(hitungBintang(true, 0.9)).toBe(3);
    expect(hitungBintang(true, 0.6)).toBe(2);
    expect(hitungBintang(false, 0.9)).toBe(1);
  });

  it('hasil percobaan memuat akurasi rata-rata, bintang, dan poin', () => {
    const cepat = new Percobaan(['a'], AMBANG_BAWAAN);
    let t = 0;
    for (let i = 0; i < 20 && !cepat.hasil(); i++, t += 50) cepat.proses({ t, fitur: BENTUK.a, suara: true });
    expect(cepat.hasil()).toMatchObject({ berhasil: true, kemiripan: 1, bintang: 3, poin: 30 });

    // Lama mencari bentuk dulu: tetap berhasil, tapi akurasinya turun.
    const lambat = new Percobaan(['a'], AMBANG_BAWAAN);
    t = 0;
    for (let i = 0; i < 40; i++, t += 50) lambat.proses({ t, fitur: DIAM, suara: true });
    for (let i = 0; i < 20 && !lambat.hasil(); i++, t += 50) lambat.proses({ t, fitur: BENTUK.a, suara: true });
    const h = lambat.hasil()!;
    expect(h.berhasil).toBe(true);
    expect(h.kemiripan).toBeLessThan(0.8);
    expect([h.bintang, h.poin]).toEqual([2, 20]);
  });

  it('keadaan tiap frame membawa kemiripan untuk bilah di layar', () => {
    const p = new Percobaan(['u'], AMBANG_BAWAAN);
    expect(p.proses({ t: 0, fitur: BENTUK.u, suara: true }).kemiripan).toBe(1);
    expect(p.proses({ t: 50, fitur: BENTUK.a, suara: true }).kemiripan).toBeLessThan(0.5);
    expect(p.proses({ t: 100, fitur: null, suara: true }).kemiripan).toBe(0);
  });
});

import {
  ABJAD, DALAM_ATAS, DALAM_BAWAH, INDEKS_BIBIR, hurufTutorial, koordinatBentuk, koordinatHuruf, semuaKoordinat,
} from '../src/tutorial';
import { FaceLandmarker } from '@mediapipe/tasks-vision';

describe('tutorial bibir a-z', () => {
  const bukaan = (h: string) => {
    const t = koordinatHuruf(h);
    return t[14]!.y - t[13]!.y;
  };
  const lebar = (h: string) => {
    const t = koordinatHuruf(h);
    return t[291]!.x - t[61]!.x;
  };

  it('ada 26 huruf dan memakai 40 titik bibir yang sama dengan MediaPipe', () => {
    expect(ABJAD.map((h) => h.huruf).join('')).toBe('abcdefghijklmnopqrstuvwxyz');
    const mp = new Set(FaceLandmarker.FACE_LANDMARKS_LIPS.flatMap((c) => [c.start, c.end]));
    expect(new Set(INDEKS_BIBIR)).toEqual(mp);
    for (const h of ABJAD) {
      const t = koordinatBentuk(h.bentuk);
      expect(Object.keys(t).map(Number).sort()).toEqual([...mp].sort());
      for (const p of Object.values(t)) {
        expect(p.x).toBeGreaterThan(0);
        expect(p.x).toBeLessThan(1);
        expect(p.y).toBeGreaterThan(0);
        expect(p.y).toBeLessThan(1);
      }
    }
    expect(Object.keys(semuaKoordinat())).toHaveLength(26);
  });

  it('bentuknya searah dengan aturan penilai', () => {
    expect(bukaan('a')).toBeGreaterThan(bukaan('o'));
    expect(bukaan('o')).toBeGreaterThan(bukaan('u'));
    expect(bukaan('m')).toBeCloseTo(0);
    expect(bukaan('b')).toBeCloseTo(0);
    expect(lebar('i')).toBeGreaterThan(lebar('a'));
    expect(lebar('a')).toBeGreaterThan(lebar('o'));
    expect(lebar('o')).toBeGreaterThan(lebar('u'));
  });

  it('bibir dalam bawah tidak pernah di atas bibir dalam atas', () => {
    for (const h of ABJAD) {
      const t = koordinatBentuk(h.bentuk);
      DALAM_ATAS.forEach((atas, i) => {
        expect(t[DALAM_BAWAH[i]!]!.y).toBeGreaterThanOrEqual(t[atas]!.y - 1e-9);
      });
    }
  });

  it('hanya huruf yang punya aturan yang ditandai dinilai, dan cocok dengan urutan bentuk', () => {
    const dinilai = ABJAD.filter((h) => h.dinilai).map((h) => h.huruf).join('');
    expect(dinilai).toBe('abimopu');
    for (const h of 'abimopu') {
      expect(urutanDariTeks(h)).toEqual([hurufTutorial(h).dinilai]);
    }
    expect(hurufTutorial('r')).toMatchObject({ bentuk: 'lidah', dinilai: null });
    expect(hurufTutorial('F')).toMatchObject({ huruf: 'f', bentuk: 'gigi_bibir' });
    expect(hurufTutorial('w').bentuk).toBe('u');
  });
});
