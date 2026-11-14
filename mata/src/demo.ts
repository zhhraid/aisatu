// Halaman uji: menyetel ambang dengan wajah sungguhan dan mencoba alur Mata -> Otak.
import { AMBANG_BAWAAN, nilaiBentuk, TEKS_PETUNJUK, urutanDariTeks, type Ambang } from './aturan';
import { Mata, type FrameMata } from './mata';
import type { HasilPercobaan, Keadaan } from './percobaan';
import { ABJAD, gambarBibir, koordinatBentuk } from './tutorial';
import { SEMUA_BUNYI, type Bunyi, type Fitur } from './tipe';

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
const NAMA_FITUR: (keyof Fitur)[] = ['rahang', 'bulat', 'lebar', 'tekan', 'celah'];

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
    const cocok = frame.fitur !== null && nilaiBentuk(bunyi, frame.fitur, mata?.ambang).cocok;
    span.classList.toggle('nyala', cocok);
  }
  for (const nama of NAMA_FITUR) {
    setUkuran(nama, frame.fitur?.[nama] ?? 0, nama === 'celah' ? 0.25 : 1);
  }
  setUkuran('suara', frame.rms, 0.2);
  el('statusSuara').textContent = mata?.mikrofonAktif
    ? `Suara: ${frame.suara ? 'ada' : 'tidak ada'} (ambang ${mata.ambangSuara.toFixed(3)})`
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

  const hasil = await mata.percobaan(urutan, tampilkanKeadaan).hasil;
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

async function panggilOtak(jalur: string, badan?: object): Promise<Record<string, unknown>> {
  const alamat = masukan('alamat').value.replace(/\/$/, '');
  const jawab = await fetch(`${alamat}/ai/anak/${encodeURIComponent(masukan('anak').value)}/${jalur}`, {
    method: 'POST',
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
  } catch (galat) {
    status.className = 'buruk';
    status.textContent = `Tidak tersambung: ${(galat as Error).message}`;
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
  el('dinilaiTutorial').textContent = data.dinilai
    ? 'Dinilai kamera.'
    : 'Hanya contoh: kamera tidak bisa menilai huruf ini.';
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
