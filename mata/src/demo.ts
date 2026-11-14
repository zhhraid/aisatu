// Halaman uji: menyetel ambang dengan wajah sungguhan dan mencoba alur Mata -> Otak.
import {
  AMBANG_BAWAAN, medianFitur, nilaiBentuk, setelOtomatis, TEKS_PETUNJUK, urutanDariTeks, type Ambang,
} from './aturan';
import { Mata, type FrameMata } from './mata';
import type { HasilPercobaan, Keadaan } from './percobaan';
import { ABJAD, gambarBibir, koordinatBentuk } from './tutorial';
import { AKURASI_MODEL_MIN, bacaModel, latihDanValidasi, layakDipakai, prediksi, type ModelBibir } from './model';
import { MatriksKebingungan, tebakAturan, tebakanTerbanyak, tebakModel } from './evaluasi';
import { PELUANG_MODEL_MIN } from './percobaan';
import { BENTUK_BIBIR, SEMUA_BUNYI, type Bunyi, type Fitur } from './tipe';

const el = <T extends HTMLElement>(id: string): T => {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Elemen #${id} tidak ada`);
  return node as T;
};
const tombol = (id: string) => el<HTMLButtonElement>(id);
const masukan = (id: string) => el<HTMLInputElement>(id);

const TEKS_POSISI = {
  ok: 'Wajah terlihat',
  tidak_ada: 'Wajah tidak terlihat',
  miring: 'Kepala terlalu miring',
  terlalu_jauh: 'Terlalu jauh dari kamera',
} as const;
const TEKS_KALIBRASI = {
  wajah_tidak_terlihat: 'Wajah tidak terlihat. Ulangi kalibrasi.',
  banyak_bergerak: 'Mulut bergerak saat kalibrasi. Ulangi sambil diam.',
  mulut_terbuka: 'Mulut terbuka saat kalibrasi. Ulangi dengan mulut tertutup.',
} as const;
const NAMA_FITUR: (keyof Fitur)[] = ['rahang', 'bulat', 'lebar', 'tekan', 'celah', 'gulung'];

let mata: Mata | null = null;
let sedangCoba = false;
/** Item dari Otak yang sedang dikerjakan, kalau tersambung. */
let itemOtak: { id: string; teks: string; urutan: Bunyi[] } | null = null;
const uji = new Map<string, { berhasil: number; jumlah: number }>();

// ---------------------------------------------------------------- tampilan

const keping = new Map<Bunyi, HTMLElement>();
for (const bunyi of SEMUA_BUNYI) {
  const span = document.createElement('span');
  span.className = 'keping';
  span.textContent = bunyi;
  el('keping').append(span);
  keping.set(bunyi, span);
}

const ukuran = new Map<string, { isi: HTMLElement; angka: HTMLElement }>();
for (const nama of [...NAMA_FITUR, 'suara']) {
  const baris = document.createElement('div');
  baris.className = 'ukur';
  baris.innerHTML = `<span>${nama}</span><div class="rel"><div class="isi"></div></div><span>0.00</span>`;
  el('ukuran').append(baris);
  ukuran.set(nama, {
    isi: baris.querySelector('.isi') as HTMLElement,
    angka: baris.lastElementChild as HTMLElement,
  });
}

function setUkuran(nama: string, nilai: number, skala = 1): void {
  const u = ukuran.get(nama);
  if (!u) return;
  u.isi.style.width = `${Math.max(0, Math.min(1, nilai / skala)) * 100}%`;
  const digit = nama === 'celah' || nama === 'suara' ? 3 : 2;
  u.angka.textContent = (Math.abs(nilai) < 0.5 / 10 ** digit ? 0 : nilai).toFixed(digit);
}

let tTampil = 0;
let tFrame = 0;
let fps = 0;
function tampilkanFrame(frame: FrameMata): void {
  // Rata-rata bergerak, supaya terlihat apakah perangkat ini cukup cepat.
  if (tFrame > 0) fps = fps * 0.9 + (1000 / Math.max(frame.t - tFrame, 1)) * 0.1;
  tFrame = frame.t;
  if (frame.t - tTampil < 100) return; // layar cukup diperbarui 10 kali per detik
  tTampil = frame.t;
  el('statusKamera').textContent = `${TEKS_POSISI[frame.posisi]} · ${fps.toFixed(0)} frame per detik`;
  for (const [bunyi, span] of keping) {
    // "h" dan desis menyala hanya kalau ada hembusan; huruf lidah kalau ada bunyi apa pun.
    const bunyiOk =
      bunyi === 'H' || bunyi === 'S' ? frame.napas : bunyi === 'T' ? frame.suara || frame.napas : true;
    let cocokBentuk = frame.fitur !== null && nilaiBentuk(bunyi, frame.fitur, mata?.ambang).cocok;
    const model = mata?.model;
    if (frame.fitur && model?.kelas.includes(bunyi)) {
      const t = prediksi(model, frame.fitur);
      cocokBentuk = t.bunyi === bunyi && (t.peluang[bunyi] ?? 0) >= PELUANG_MODEL_MIN;
    }
    const cocok = cocokBentuk && bunyiOk;
    span.classList.toggle('nyala', cocok);
  }
  for (const nama of NAMA_FITUR) {
    setUkuran(nama, frame.fitur?.[nama] ?? 0, nama === 'celah' ? 0.25 : 1);
  }
  setUkuran('suara', frame.rms, 0.2);
  el('statusSuara').textContent = mata?.mikrofonAktif
    ? `Suara: ${frame.suara ? 'ada' : 'tidak ada'} (ambang ${mata.ambangSuara.toFixed(3)}) · hembusan: ${frame.napas ? 'ada' : 'tidak ada'}`
    : 'Mikrofon tidak aktif. Centang "Abaikan suara" untuk menguji bentuk bibir.';
}

function tampilkanUrutan(): Bunyi[] {
  const teks = masukan('target').value.trim();
  const urutan = itemOtak?.teks === teks ? itemOtak.urutan : teks === 'M' ? ['M' as Bunyi] : urutanDariTeks(teks);
  el('urutan').textContent = urutan.length ? urutan.join(' , ') : '(tidak ada bentuk yang bisa dinilai)';
  return urutan;
}

function tampilkanUji(): void {
  el('tabelUji').innerHTML = [...uji]
    .map(([target, u]) => `<tr><td>${target}</td><td>${u.berhasil}</td><td>${u.jumlah}</td></tr>`)
    .join('');
}

function tampilkanKeadaan(k: Keadaan): void {
  (el('progres').firstElementChild as HTMLElement).style.width = `${k.progres * 100}%`;
  (el('kemiripan').firstElementChild as HTMLElement).style.width = `${k.kemiripan * 100}%`;
  el('angkaKemiripan').textContent = `${Math.round(k.kemiripan * 100)}%`;
  const petunjuk = el('petunjuk');
  if (k.status === 'jeda') petunjuk.textContent = 'Jeda: wajah tidak terlihat';
  else if (k.petunjuk === 'bersuara') petunjuk.textContent = 'Bentuk sudah benar, sekarang bersuara';
  else if (k.petunjuk === 'hembuskan') petunjuk.textContent = 'Hembuskan napas (seperti meniup tisu)';
  else if (k.petunjuk === 'desiskan') petunjuk.textContent = 'Desiskan udara lewat gigi (sss)';
  else if (k.petunjuk) petunjuk.textContent = TEKS_PETUNJUK[k.petunjuk];
  else petunjuk.textContent = k.status === 'berjalan' ? 'Tahan...' : '';
}

// ----------------------------------------------------------------- tindakan

tombol('tombolKamera').addEventListener('click', async () => {
  const t = tombol('tombolKamera');
  t.disabled = true;
  el('statusKamera').textContent = 'Memuat model...';
  try {
    mata = await Mata.buat({ wasmPath: '/wasm', modelPath: '/model/face_landmarker.task' });
    await mata.mulaiKamera(el<HTMLVideoElement>('video'));
    mata.padaFrame(tampilkanFrame);
    tombol('tombolKalibrasi').disabled = false;
    tombol('tombolCoba').disabled = false;
    tombol('tombolSetel').disabled = false;
    tombol('tombolRekam').disabled = false;
    tombol('tombolBerpandu').disabled = false;
    el('statusKalibrasi').textContent = 'Belum dikalibrasi: angka di samping masih mentah.';
    t.textContent = 'Kamera aktif';
    document.body.dataset['siap'] = '1';
  } catch (galat) {
    el('statusKamera').textContent = `Gagal: ${(galat as Error).message}`;
    t.disabled = false;
  }
});

tombol('tombolKalibrasi').addEventListener('click', async () => {
  if (!mata) return;
  const status = el('statusKalibrasi');
  tombol('tombolKalibrasi').disabled = true;
  const hasil = await mata.kalibrasi((bagian) => {
    status.textContent = `Diam, mulut tertutup... ${Math.round(bagian * 100)}%`;
  });
  status.className = hasil.ok ? 'baik' : 'buruk';
  status.textContent = hasil.ok ? 'Kalibrasi selesai.' : TEKS_KALIBRASI[hasil.alasan];
  document.body.dataset['kalibrasi'] = hasil.ok ? 'ok' : hasil.alasan;
  tombol('tombolKalibrasi').disabled = false;
});

masukan('target').addEventListener('input', () => {
  itemOtak = null;
  tampilkanUrutan();
});

tombol('tombolCoba').addEventListener('click', async () => {
  if (!mata || sedangCoba) return;
  const urutan = tampilkanUrutan();
  if (urutan.length === 0) return;
  sedangCoba = true;
  tombol('tombolCoba').disabled = true;
  el('hasil').textContent = '';
  const target = masukan('target').value.trim();
  mata.aturPercobaan({ tanpaSuara: masukan('tanpaSuara').checked });

  const pembaruanSebelum = mata.model?.pembaruan ?? 0;
  const hasil = await mata.percobaan(urutan, tampilkanKeadaan).hasil;
  if (mata.model && (mata.model.pembaruan ?? 0) > pembaruanSebelum) {
    modelTerlatih = mata.model;
    el('statusModel').textContent =
      `Model personal belajar dari percobaan ini (${mata.model.pembaruan} kali sejak dilatih). ` +
      'Tekan "Simpan model ke Otak" untuk menyimpannya.';
  }
  sedangCoba = false;
  tombol('tombolCoba').disabled = false;
  if (!hasil) return;
  const catatan = uji.get(target) ?? { berhasil: 0, jumlah: 0 };
  catatan.jumlah += 1;
  catatan.berhasil += hasil.berhasil ? 1 : 0;
  uji.set(target, catatan);
  tampilkanUji();
  const teksHasil = el('hasil');
  teksHasil.className = hasil.berhasil ? 'baik' : 'buruk';
  const nilai = `${'★'.repeat(hasil.bintang)}${'☆'.repeat(3 - hasil.bintang)} · akurasi ${Math.round(hasil.kemiripan * 100)}% · ${hasil.poin} poin`;
  teksHasil.textContent = hasil.berhasil
    ? `Berhasil dalam ${(hasil.durasi_ms / 1000).toFixed(1)} detik. ${nilai}`
    : `Gagal: macet di langkah ${hasil.langkah_tercapai + 1} dari ${urutan.length}. ${nilai}`;
  document.body.dataset['hasil'] = JSON.stringify(hasil);
  if (itemOtak) await kirimKeOtak(itemOtak.id, hasil);
});

// Ambang
const kotakAmbang = el<HTMLTextAreaElement>('ambang');
kotakAmbang.value = JSON.stringify(AMBANG_BAWAAN, null, 2);
tombol('terapkanAmbang').addEventListener('click', () => {
  const status = el('statusAmbang');
  try {
    const baru = JSON.parse(kotakAmbang.value) as Ambang;
    for (const bunyi of SEMUA_BUNYI) {
      const lama = AMBANG_BAWAAN[bunyi] as Record<string, number>;
      const isi = baru[bunyi] as Record<string, unknown> | undefined;
      for (const kunci of Object.keys(lama)) {
        if (typeof isi?.[kunci] !== 'number') throw new Error(`${bunyi}.${kunci} harus angka`);
      }
    }
    if (mata) mata.ambang = baru;
    status.className = 'baik';
    status.textContent = mata ? 'Diterapkan.' : 'Tersimpan, berlaku setelah kamera mulai.';
  } catch (galat) {
    status.className = 'buruk';
    status.textContent = (galat as Error).message;
  }
});
tombol('salinAmbang').addEventListener('click', () => navigator.clipboard.writeText(kotakAmbang.value));
tombol('salinUji').addEventListener('click', () =>
  navigator.clipboard.writeText(
    ['target\tberhasil\tjumlah', ...[...uji].map(([t, u]) => `${t}\t${u.berhasil}\t${u.jumlah}`)].join('\n'),
  ),
);
tombol('resetUji').addEventListener('click', () => {
  uji.clear();
  tampilkanUji();
});

// ------------------------------------------------------------ sambung ke Otak

interface PilihanOtak {
  item: { id: string; teks: string; tingkat: number; urutan: Bunyi[] };
  perkiraan_berhasil: number;
  alasan: string;
  istirahat: boolean;
}

function pakaiPilihan(pilihan: PilihanOtak): void {
  itemOtak = pilihan.item;
  masukan('target').value = pilihan.item.teks;
  tampilkanUrutan();
  el('pilihanOtak').textContent =
    `Latihan dari Otak: "${pilihan.item.teks}" (tingkat ${pilihan.item.tingkat}), ` +
    `perkiraan berhasil ${Math.round(pilihan.perkiraan_berhasil * 100)}%, alasan: ${pilihan.alasan}` +
    (pilihan.istirahat ? '. Waktunya istirahat sebentar.' : '.');
}

async function panggilOtak(jalur: string, badan?: object, metode = 'POST'): Promise<Record<string, unknown>> {
  const alamat = masukan('alamat').value.replace(/\/$/, '');
  const jawab = await fetch(`${alamat}/ai/anak/${encodeURIComponent(masukan('anak').value)}/${jalur}`, {
    method: metode,
    headers: { 'Content-Type': 'application/json' },
    body: badan ? JSON.stringify(badan) : undefined,
  });
  if (!jawab.ok) throw new Error(`Otak menjawab ${jawab.status}`);
  return (await jawab.json()) as Record<string, unknown>;
}

async function kirimKeOtak(itemId: string, hasil: HasilPercobaan): Promise<void> {
  const status = el('statusOtak');
  try {
    const jawab = await panggilOtak('percobaan', { item_id: itemId, ...hasil });
    status.className = 'baik';
    status.textContent = 'Hasil terkirim.';
    pakaiPilihan(jawab['berikutnya'] as PilihanOtak);
  } catch (galat) {
    status.className = 'buruk';
    status.textContent = `Tidak terkirim: ${(galat as Error).message}`;
  }
}

tombol('tombolSesi').addEventListener('click', async () => {
  const status = el('statusOtak');
  try {
    const jawab = await panggilOtak('sesi');
    status.className = 'baik';
    status.textContent = 'Tersambung.';
    pakaiPilihan(jawab['berikutnya'] as PilihanOtak);
    // Model personal anak ini, kalau pernah disimpan.
    const tersimpan = bacaModel((await panggilOtak('model-bibir', undefined, 'GET'))['model']);
    if (tersimpan && mata) {
      pasangModel(tersimpan, 'Model personal anak ini dimuat dari Otak.');
    }
  } catch (galat) {
    status.className = 'buruk';
    status.textContent = `Tidak tersambung: ${(galat as Error).message}`;
  }
});

tombol('simpanModel').addEventListener('click', async () => {
  const status = el('statusOtak');
  if (!mata?.model) return;
  try {
    await panggilOtak('model-bibir', { model: mata.model }, 'PUT');
    status.className = 'baik';
    status.textContent = 'Model personal tersimpan untuk anak ini.';
  } catch (galat) {
    status.className = 'buruk';
    status.textContent = `Model tidak tersimpan: ${(galat as Error).message}`;
  }
});

tampilkanUrutan();

// ------------------------------------------------------------- tutorial a-z

const kanvasTutorial = el<HTMLCanvasElement>('kanvasTutorial');
function pilihHuruf(huruf: string): void {
  const data = ABJAD.find((h) => h.huruf === huruf);
  if (!data) return;
  const ctx = kanvasTutorial.getContext('2d');
  if (ctx) gambarBibir(ctx, koordinatBentuk(data.bentuk));
  el('hurufTutorial').textContent = data.huruf.toUpperCase();
  el('petunjukTutorial').textContent = data.petunjuk;
  el('dinilaiTutorial').textContent = !data.dinilai
    ? 'Hanya contoh: kamera tidak bisa menilai huruf ini.'
    : data.sebagian
      ? 'Dinilai sebagian: posisi mulut dan suaranya, bukan lidah. Ketepatan lidah dinilai guru.'
      : 'Dinilai kamera.';
  for (const tombolHuruf of el('abjad').querySelectorAll('button')) {
    tombolHuruf.classList.toggle('pilih', tombolHuruf.textContent === data.huruf);
  }
}
for (const h of ABJAD) {
  const b = document.createElement('button');
  b.textContent = h.huruf;
  b.addEventListener('click', () => pilihHuruf(h.huruf));
  el('abjad').append(b);
}
pilihHuruf('a');

// ---------------------------------------------------------- setel otomatis

type BentukBibir = Exclude<Bunyi, 'H' | 'S' | 'T'>;
const NAMA_BENTUK: Record<BentukBibir, string> = {
  a: '"aaa", mulut terbuka lebar',
  i: '"iii", bibir ditarik ke samping',
  u: '"uuu", bibir mengerucut',
  o: '"ooo", bibir bulat dan agak terbuka',
  M: '"mmm", bibir rapat',
  e: '"eee", mulut terbuka sedikit',
  F: '"fff", gigi atas menempel di bibir bawah',
};
const tunggu = (ms: number) => new Promise((selesai) => setTimeout(selesai, ms));

async function kumpulkanBentuk(lamaMs: number): Promise<Fitur[]> {
  const frame: Fitur[] = [];
  const lepas = mata!.padaFrame((f) => {
    if (f.fitur) frame.push(f.fitur);
  });
  await tunggu(lamaMs);
  lepas();
  return frame;
}

tombol('tombolSetel').addEventListener('click', async () => {
  const arahan = el('arahanSetel');
  const status = el('statusSetel');
  status.className = '';
  status.textContent = '';
  if (!mata?.terkalibrasi) {
    status.className = 'buruk';
    status.textContent = 'Kalibrasi dulu (tombol Kalibrasi di kartu 1).';
    return;
  }
  tombol('tombolSetel').disabled = true;
  const contoh = {} as Record<BentukBibir, Fitur>;
  const contohFrame = {} as Record<BentukBibir, Fitur[]>;
  try {
    for (const bunyi of BENTUK_BIBIR as BentukBibir[]) {
      pilihHuruf(bunyi === 'M' ? 'm' : bunyi === 'F' ? 'f' : bunyi);
      for (let hitung = 3; hitung > 0; hitung--) {
        arahan.textContent = `Siap-siap: ${NAMA_BENTUK[bunyi]} (${hitung})`;
        await tunggu(600);
      }
      arahan.textContent = `Tahan ${NAMA_BENTUK[bunyi]}...`;
      const frame = await kumpulkanBentuk(2000);
      if (frame.length < 5) throw new Error(`Wajah tidak terlihat saat bentuk ${bunyi}. Ulangi.`);
      contoh[bunyi] = medianFitur(frame);
      contohFrame[bunyi] = frame;
    }
    arahan.textContent = '';
    latihModelPersonal(contohFrame);
    const hasil = setelOtomatis(contoh);
    if (!hasil.ok) {
      status.className = 'buruk';
      status.innerHTML = 'Belum bisa disetel:<br>' + hasil.masalah.map((m) => `- ${m}`).join('<br>');
      return;
    }
    const bulat = JSON.parse(JSON.stringify(hasil.ambang, (_k, v) => (typeof v === 'number' ? Math.round(v * 1000) / 1000 : v)));
    mata.ambang = bulat as Ambang;
    kotakAmbang.value = JSON.stringify(bulat, null, 2);
    status.className = 'baik';
    status.textContent = 'Ambang disetel dari wajahmu dan langsung dipakai. Coba lima bentuk lagi, lalu tekan Salin untuk menyimpannya.';
    document.body.dataset['setel'] = 'ok';
  } catch (galat) {
    arahan.textContent = '';
    status.className = 'buruk';
    status.textContent = (galat as Error).message;
  } finally {
    tombol('tombolSetel').disabled = false;
  }
});

// ------------------------------------------------------------ model personal

function pasangModel(model: ModelBibir, pesan: string): void {
  if (!mata) return;
  modelTerlatih = model;
  const layak = layakDipakai(model);
  // Model yang kurang akurat tidak dipakai otomatis; aturan ambang tetap jadi penilai.
  mata.model = layak ? model : null;
  masukan('pakaiModel').disabled = false;
  masukan('pakaiModel').checked = layak;
  tombol('simpanModel').disabled = !layak;
  const st = el('statusModel');
  st.className = layak ? 'baik' : 'peringatan';
  st.textContent = layak
    ? pesan
    : `${pesan} Belum cukup akurat (minimal ${Math.round(AKURASI_MODEL_MIN * 100)}%), jadi penilaian tetap ` +
      'memakai aturan. Ulangi Setel otomatis dengan tiap bentuk dibuat lebih jelas.';
}

let modelTerlatih: ModelBibir | null = null;

function latihModelPersonal(contohFrame: Record<BentukBibir, Fitur[]>): void {
  const st = el('statusModel');
  try {
    const { model, validasi: v } = latihDanValidasi(contohFrame);
    const per = (Object.entries(v.perKelas) as [Bunyi, number][])
      .map(([b, a]) => `${b} ${Math.round(a * 100)}%`)
      .join(', ');
    pasangModel(
      model,
      `Model personal dilatih dari ${v.jumlah} contoh wajahmu. Akurasi validasi silang: ` +
        `${Math.round(v.akurasi * 100)}% (${per}).`,
    );
    document.body.dataset['model'] = String(Math.round(v.akurasi * 100));
  } catch (galat) {
    st.className = 'buruk';
    st.textContent = `Model personal belum bisa dilatih: ${(galat as Error).message}`;
  }
}

masukan('pakaiModel').addEventListener('change', () => {
  if (mata) mata.model = masukan('pakaiModel').checked ? modelTerlatih : null;
  tampilkanAkurasi();
});

// --------------------------------------------------------------- uji akurasi

const matriksAturan = new MatriksKebingungan();
const matriksModel = new MatriksKebingungan();
const pilihTarget = el<HTMLSelectElement>('targetUji');
for (const b of BENTUK_BIBIR as BentukBibir[]) {
  const pilihan = document.createElement('option');
  pilihan.value = b;
  pilihan.textContent = NAMA_BENTUK[b];
  pilihTarget.append(pilihan);
}

function tampilkanAkurasi(): void {
  const persen = (x: number | null) => (x === null ? '-' : `${Math.round(x * 100)}%`);
  const keteranganModel = mata?.model
    ? persen(matriksModel.akurasi())
    : modelTerlatih
      ? `tidak dipakai (akurasi validasi ${Math.round((modelTerlatih.akurasi ?? 0) * 100)}%, di bawah ${Math.round(AKURASI_MODEL_MIN * 100)}%)`
      : 'belum ada model (jalankan Setel otomatis)';
  el('ringkasUji').textContent =
    `${matriksAturan.jumlah} rekaman. Akurasi aturan: ${persen(matriksAturan.akurasi())}. ` +
    `Akurasi model personal: ${keteranganModel}` +
    (matriksModel.jumlah && matriksModel.jumlah !== matriksAturan.jumlah
      ? ` (dari ${matriksModel.jumlah} rekaman saat model dipakai).`
      : '.');
  el('tabelAturan').textContent = matriksAturan.jumlah ? matriksAturan.keTsv() : '';
  el('tabelModel').textContent = matriksModel.jumlah ? matriksModel.keTsv() : '';
}

/** Merekam satu bentuk 2 detik dan mencatat tebakan aturan dan model personal. */
async function rekamSatu(target: BentukBibir, awalan = ''): Promise<void> {
  const arahan = el('arahanUji');
  pilihHuruf(target === 'M' ? 'm' : target === 'F' ? 'f' : target);
  for (let hitung = 3; hitung > 0; hitung--) {
    arahan.textContent = `${awalan}Siap-siap: ${NAMA_BENTUK[target]} (${hitung})`;
    await tunggu(500);
  }
  arahan.textContent = `${awalan}Tahan ${NAMA_BENTUK[target]}...`;
  const frame = await kumpulkanBentuk(2000);
  if (frame.length < 5) throw new Error('Wajah tidak terlihat. Ulangi.');
  matriksAturan.tambah(target, tebakanTerbanyak(frame.map((f) => tebakAturan(f, mata!.ambang))));
  // Hanya model yang layak dan sedang dipakai yang dinilai; model yang belum cukup akurat
  // tidak dipakai menilai anak, jadi tidak adil ikut dihitung.
  const model = mata!.model;
  if (model) matriksModel.tambah(target, tebakanTerbanyak(frame.map((f) => tebakModel(f, model))));
  arahan.textContent = '';
  tampilkanAkurasi();
}

function kunciUji(kunci: boolean): void {
  tombol('tombolRekam').disabled = kunci;
  tombol('tombolBerpandu').disabled = kunci;
}

tombol('tombolRekam').addEventListener('click', async () => {
  if (!mata) return;
  kunciUji(true);
  try {
    await rekamSatu(pilihTarget.value as BentukBibir);
  } catch (galat) {
    el('arahanUji').textContent = (galat as Error).message;
  } finally {
    kunciUji(false);
  }
});

const PUTARAN_BERPANDU = 3;

tombol('tombolBerpandu').addEventListener('click', async () => {
  if (!mata) return;
  if (!mata.terkalibrasi) {
    el('arahanUji').textContent = 'Kalibrasi dulu (tombol Kalibrasi di kartu 1).';
    return;
  }
  kunciUji(true);
  // Urutan acak supaya penguji tidak sekadar mengulang bentuk yang sama berturut-turut.
  const daftar = Array.from({ length: PUTARAN_BERPANDU }, () => [...BENTUK_BIBIR] as BentukBibir[])
    .flatMap((putaran) => putaran.sort(() => Math.random() - 0.5));
  try {
    for (let i = 0; i < daftar.length; i++) {
      await rekamSatu(daftar[i]!, `${i + 1}/${daftar.length} · `);
    }
    el('arahanUji').textContent = 'Uji berpandu selesai. Tekan "Salin tabel" untuk slide.';
    document.body.dataset['uji'] = 'selesai';
  } catch (galat) {
    el('arahanUji').textContent = (galat as Error).message;
  } finally {
    kunciUji(false);
  }
});

tombol('salinAkurasi').addEventListener('click', () =>
  navigator.clipboard.writeText(
    `${el('ringkasUji').textContent}\n\nAturan\n${matriksAturan.keTsv()}\n\nModel personal\n${matriksModel.keTsv()}`,
  ),
);
tombol('kosongAkurasi').addEventListener('click', () => {
  matriksAturan.kosongkan();
  matriksModel.kosongkan();
  tampilkanAkurasi();
});
tampilkanAkurasi();
