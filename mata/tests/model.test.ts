import { describe, expect, it } from 'vitest';
import { AMBANG_BAWAAN } from '../src/aturan';
import { MatriksKebingungan, tebakAturan, tebakanTerbanyak, tebakModel } from '../src/evaluasi';
import { bacaModel, JARAK_ASING, latihDanValidasi, latihModel, layakDipakai, perbaruiModel, prediksi, validasiSilang } from '../src/model';
import { Percobaan } from '../src/percobaan';
import type { Bunyi, Fitur } from '../src/tipe';

type BentukBibir = Exclude<Bunyi, 'h' | 's' | 't'>;
// Bentuk satu anak yang gerakannya kecil (di bawah ambang bawaan untuk sebagian bentuk).
const PUSAT: Record<BentukBibir, Fitur> = {
  a: { rahang: 0.22, bulat: 0.03, lebar: 0.04, tekan: 0, celah: 0.09, gulung: 0 },
  i: { rahang: 0.05, bulat: 0.02, lebar: 0.13, tekan: 0, celah: 0.025, gulung: 0 },
  u: { rahang: 0.03, bulat: 0.28, lebar: 0, tekan: 0, celah: 0.015, gulung: 0 },
  o: { rahang: 0.13, bulat: 0.2, lebar: 0, tekan: 0, celah: 0.05, gulung: 0 },
  m: { rahang: 0.01, bulat: 0.04, lebar: 0.02, tekan: 0.08, celah: 0.003, gulung: 0.02 },
  e: { rahang: 0.13, bulat: 0.02, lebar: 0.1, tekan: 0, celah: 0.045, gulung: 0 },
  f: { rahang: 0.02, bulat: 0.03, lebar: 0.03, tekan: 0.06, celah: 0.008, gulung: 0.2 },
};

/** Contoh berderau di sekitar pusat, seperti frame kamera sungguhan. */
function contoh(seed = 1, n = 30, derau = 0.015): Record<BentukBibir, Fitur[]> {
  let s = seed;
  const acak = () => ((s = (s * 16807) % 2147483647) / 2147483647 - 0.5) * 2;
  const hasil = {} as Record<BentukBibir, Fitur[]>;
  for (const [b, p] of Object.entries(PUSAT) as [BentukBibir, Fitur][]) {
    hasil[b] = Array.from({ length: n }, () => ({
      rahang: p.rahang + acak() * derau, bulat: p.bulat + acak() * derau, lebar: p.lebar + acak() * derau,
      tekan: p.tekan + acak() * derau, celah: Math.max(0, p.celah + acak() * derau * 0.3), gulung: (p.gulung ?? 0) + acak() * derau,
    }));
  }
  return hasil;
}

describe('model bibir personal', () => {
  it('dilatih dari contoh satu anak dan mengenali tiap bentuknya', () => {
    const model = latihModel(contoh());
    expect(model.kelas).toEqual(['a', 'i', 'u', 'o', 'm', 'e', 'f']);
    for (const [b, p] of Object.entries(PUSAT)) {
      const t = prediksi(model, p);
      expect(t.bunyi, b).toBe(b);
      expect(t.peluang[b as Bunyi]!).toBeGreaterThan(0.9);
    }
  });

  it('validasi silang memberi akurasi dan tabel kesalahan', () => {
    const v = validasiSilang(contoh(3));
    expect(v.jumlah).toBe(7 * 30);
    expect(v.akurasi).toBeGreaterThan(0.95);
    expect(v.matriks['a']!['a']).toBeGreaterThan(25);
  });

  it('bentuk yang jauh dari semua kelas tidak dikenali', () => {
    const model = latihModel(contoh());
    const aneh: Fitur = { rahang: 0.9, bulat: 0.9, lebar: 0.9, tekan: 0.9, celah: 0.3, gulung: 0.9 };
    const t = prediksi(model, aneh);
    expect(t.bunyi).toBeNull();
    expect(t.jarak).toBeGreaterThan(JARAK_ASING);
  });

  it('lebih tepat daripada aturan bawaan untuk anak yang gerakannya kecil', () => {
    const uji = contoh(99, 20);
    const model = latihModel(contoh(7));
    let benarModel = 0;
    let benarAturan = 0;
    let total = 0;
    for (const [b, daftar] of Object.entries(uji)) {
      for (const f of daftar) {
        total++;
        benarModel += tebakModel(f, model) === b ? 1 : 0;
        benarAturan += tebakAturan(f, AMBANG_BAWAAN) === b ? 1 : 0;
      }
    }
    expect(benarModel / total).toBeGreaterThan(0.95);
    expect(benarAturan / total).toBeLessThan(benarModel / total);
  });

  it('disimpan dan dibaca kembali sebagai JSON, dan JSON rusak ditolak', () => {
    const model = latihModel(contoh());
    expect(bacaModel(JSON.parse(JSON.stringify(model)))).toEqual(model);
    expect(bacaModel({ versi: 1, kelas: ['a'], pusat: [], skala: [] })).toBeNull();
    expect(bacaModel(null)).toBeNull();
  });

  it('percobaan memakai model personal kalau tersedia', () => {
    const model = latihModel(contoh());
    const jalankan = (opsi: object) => {
      const p = new Percobaan(['a'], AMBANG_BAWAAN, opsi);
      for (let i = 0, t = 0; i < 30 && !p.hasil(); i++, t += 50) p.proses({ t, fitur: PUSAT.a, suara: true });
      return p.hasil();
    };
    expect(jalankan({})).toBeNull(); // aturan bawaan: "a" anak ini terlalu kecil
    expect(jalankan({ model })?.berhasil).toBe(true); // model personal: dikenali
  });

  it('model menolak bentuk yang lolos aturan tapi bukan bentuk anak ini untuk bunyi itu', () => {
    const model = latihModel(contoh());
    const p = new Percobaan(['a'], AMBANG_BAWAAN, { model });
    const k = p.proses({ t: 0, fitur: PUSAT.o, suara: true });
    expect(k.cocok).toBe(false);
    expect(k.petunjuk).not.toBeNull();
  });
});

describe('alat ukur akurasi', () => {
  it('tabel kebingungan menghitung akurasi dan per target', () => {
    const m = new MatriksKebingungan();
    m.tambah('a', 'a');
    m.tambah('a', 'o');
    m.tambah('u', 'u');
    m.tambah('u', null);
    expect(m.jumlah).toBe(4);
    expect(m.akurasi()).toBe(0.5);
    expect(m.perTarget()).toEqual([
      { target: 'a', benar: 1, jumlah: 2 },
      { target: 'u', benar: 1, jumlah: 2 },
    ]);
    expect(m.keTsv().split('\n')[0]).toBe('target \\ tebakan\ta\tu\to\t?');
    m.kosongkan();
    expect(m.akurasi()).toBeNull();
  });

  it('tebakan rekaman diambil dari suara terbanyak', () => {
    expect(tebakanTerbanyak(['a', 'a', 'o', null, 'a'])).toBe('a');
    expect(tebakanTerbanyak([null, null, 'u'])).toBeNull();
  });
});

describe('pengaman model', () => {
  it('model dari contoh yang jelas layak dipakai; dari bentuk yang tidak dibedakan tidak', () => {
    const baik = latihDanValidasi(contoh());
    expect(baik.model.akurasi).toBeGreaterThan(0.95);
    expect(layakDipakai(baik.model)).toBe(true);

    // Semua "bentuk" sama (anak tidak mengikuti arahan saat Setel otomatis).
    const sama = contoh(5);
    for (const b of Object.keys(sama) as BentukBibir[]) sama[b] = contoh(5 + b.charCodeAt(0)).a;
    const buruk = latihDanValidasi(sama);
    expect(buruk.model.akurasi).toBeLessThan(0.5);
    expect(layakDipakai(buruk.model)).toBe(false);
    expect(layakDipakai(latihModel(contoh()))).toBe(false); // tanpa akurasi: tidak dipakai
    expect(layakDipakai(null)).toBe(false);
  });
});

describe('model terus belajar dari latihan', () => {
  it('contoh yang yakin dan dekat menggeser titik tengah pelan-pelan', () => {
    const model = latihModel(contoh());
    const geser: Fitur = { ...PUSAT.a, rahang: PUSAT.a.rahang + 0.02 };
    const baru = perbaruiModel(model, 'a', geser)!;
    expect(baru).not.toBeNull();
    const k = model.kelas.indexOf('a');
    expect(baru.pusat[k]![0]).toBeGreaterThan(model.pusat[k]![0]!);
    expect(baru.pusat[k]![0]! - model.pusat[k]![0]!).toBeLessThan(0.002); // satu contoh: geser kecil
    expect(baru.pusat[1]).toEqual(model.pusat[1]); // bentuk lain tidak berubah
    expect([baru.pembaruan, baru.jumlah[k]]).toEqual([1, model.jumlah[k]! + 1]);
  });

  it('contoh yang bukan bentuk itu atau jauh dari yang dikenal ditolak', () => {
    const model = latihModel(contoh());
    expect(perbaruiModel(model, 'a', PUSAT.o)).toBeNull(); // model mengira "o"
    const jauh: Fitur = { ...PUSAT.a, rahang: 0.6 };
    expect(perbaruiModel(model, 'a', jauh)).toBeNull();
    expect(perbaruiModel(model, 'h', PUSAT.a)).toBeNull(); // "h" bukan kelas model
  });

  it('banyak latihan membuat model mengikuti perubahan wajah anak', () => {
    let model = latihModel(contoh());
    const k = model.kelas.indexOf('a');
    for (let i = 0; i < 200; i++) {
      model = perbaruiModel(model, 'a', { ...PUSAT.a, rahang: PUSAT.a.rahang + 0.03 }) ?? model;
    }
    expect(model.pusat[k]![0]).toBeCloseTo(PUSAT.a.rahang + 0.03, 2);
  });

  it('percobaan bunyi tunggal yang berhasil menyertakan contoh bentuk', () => {
    const p = new Percobaan(['a'], AMBANG_BAWAAN, { model: latihModel(contoh()) });
    for (let i = 0, t = 0; i < 30 && !p.hasil(); i++, t += 50) p.proses({ t, fitur: PUSAT.a, suara: true });
    expect(p.hasil()!.contoh!.rahang).toBeCloseTo(PUSAT.a.rahang);
    const kata = new Percobaan(['m', 'a'], AMBANG_BAWAAN);
    kata.proses({ t: 0, fitur: PUSAT.m, suara: false });
    kata.proses({ t: 50, fitur: PUSAT.m, suara: false });
    expect(kata.hasil()).toBeNull();
  });
});

describe('kode bunyi huruf kecil', () => {
  it('model lama berkode huruf besar dibaca sebagai huruf kecil', () => {
    const lama = { versi: 1, kelas: ['a', 'M', 'F'], pusat: [[0.3], [0], [0.1]], skala: [0.05], jumlah: [5, 5, 5] };
    expect(bacaModel(lama)!.kelas).toEqual(['a', 'm', 'f']);
  });
});
