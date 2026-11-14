# SATU: lapis AI

Tiga lapis AI untuk platform bina wicara anak tunarungu, tanpa model yang dilatih sendiri.

| Lapis | Tugas | Tempat jalan | Folder |
| --- | --- | --- | --- |
| Mata | Menilai bentuk bibir dan mendeteksi suara | Browser (MediaPipe + aturan) | `mata/` |
| Otak | Penguasaan per bunyi (BKT), memilih latihan, usulan tugas | Backend Python | `backend/satu_ai/otak.py` |
| Mulut | Alasan tugas, ringkasan kelas, laporan orang tua | Backend Python (LLM + templat cadangan) | `backend/satu_ai/mulut.py` |

Video dan suara tidak pernah keluar dari browser. Yang dikirim ke backend hanya hasil tiap percobaan.

## Status

Sudah diuji:

- Backend: 117 tes otomatis (rumus BKT, pemilih latihan, usulan tugas, pagar keluaran LLM, semua endpoint).
- Mata: 53 tes otomatis (aturan bibir, fitur, kalibrasi, penilai percobaan, penentu suara).
- Alur penuh di Chromium dengan kamera tiruan (foto wajah contoh sebagai video): model termuat, wajah terbaca, kalibrasi berhasil, percobaan dinilai, hasil terkirim ke Otak, Otak memilih latihan berikutnya.

Belum diuji, dan harus kalian lakukan:

- **Ambang aturan bibir belum diuji dengan wajah yang bergerak.** Angka bawaan di `mata/src/aturan.ts` ditentukan dari perilaku blendshape MediaPipe saat bicara biasa, bukan dari pengukuran, dan dijamin tidak tumpang tindih (tes `cekTumpang`). Untuk wajah tertentu, pakai **Setel otomatis** di halaman uji.
- **Belum pernah dicoba pada anak tunarungu.**
- **Panggilan ke Gemini sungguhan.** Klien HTTP-nya diuji dengan server tiruan dan alamat Gemini sudah dipastikan ada, tapi belum pernah dipanggil dengan kunci API asli.
- **Kecepatan di HP.** Di lingkungan uji tanpa GPU hanya 6 sampai 9 frame per detik. Halaman uji menampilkan angka ini; cek di laptop sekolah dan HP Android murah.

## Menjalankan backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

Di Windows (PowerShell), dari folder `backend`:

```bash
python -m venv .venv
```

```bash
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
copy .env.example .env
```

```bash
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

Berkas `.env` harus berada di folder `backend`, bukan di folder utama repo. Backend membacanya sendiri saat dinyalakan, jadi setiap perubahan `.env` perlu menyalakan ulang backend. Buka `http://localhost:8000/ai/status` untuk melihat apakah berkasnya terbaca dan pengaturan mana yang masih kosong. Dokumentasi endpoint otomatis ada di `http://localhost:8000/docs`.

Tes:

```bash
.venv/bin/python -m pytest -q
```

Isi `.env`:

| Variabel | Isi |
| --- | --- |
| `LLM_BASE_URL` | Alamat API yang kompatibel dengan OpenAI. Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`. Groq: `https://api.groq.com/openai/v1` |
| `LLM_API_KEY` | Kunci API (untuk Gemini: dari Google AI Studio). Hanya di server, jangan di-commit |
| `LLM_MODEL` | Nama model di penyedia itu, misalnya `gemini-3.5-flash-lite` |
| `LLM_REASONING_EFFORT` | Opsional: `minimal`, `low`, `medium`, `high`. Untuk Gemini 3 pakai `low` supaya cepat |
| `LLM_MAKS_TOKEN` | Batas token keluaran, bawaan 2000. Model yang berpikir dulu memakai sebagian untuk berpikir |
| `LLM_BATAS_DETIK` | Batas waktu satu panggilan, bawaan 12 |
| `SATU_DEMO` | `1` = pemilihan latihan tanpa acak dan endpoint data demo aktif |

Kalau tiga variabel pertama kosong, atau panggilan gagal, semua teks memakai templat. Field `sumber` di jawaban berisi `llm` atau `templat`. Kalau hasilnya `templat` padahal kunci sudah diisi, penyebabnya tercetak di log backend: kode HTTP dari penyedia, keluaran yang terpotong, atau keluaran yang ditolak pagar.

## Endpoint

Semua di bawah `/ai`. Belum ada login; tambahkan saat router dipasang ke aplikasi utama.

| Metode dan jalur | Dipakai oleh | Isi |
| --- | --- | --- |
| `GET /ai/kurikulum` | web, mobile | Daftar bunyi, tingkat, dan 46 item latihan |
| `POST /ai/anak/{id}/sesi` | web siswa | Mulai sesi, mengembalikan latihan pertama |
| `POST /ai/anak/{id}/percobaan` | web siswa | Kirim satu hasil, mengembalikan perubahan penguasaan dan latihan berikutnya |
| `GET /ai/anak/{id}/berikutnya` | web siswa | Latihan berikutnya tanpa mengubah apa pun |
| `GET /ai/anak/{id}/peta` | mobile guru, web orang tua | Penguasaan per bunyi, label, warna, bunyi macet dan naik |
| `POST /ai/anak/{id}/tugas-usulan` | mobile guru | 3 latihan rumah beserta alasannya |
| `POST /ai/anak/{id}/laporan-mingguan` | web orang tua | Laporan tiga bagian |
| `POST /ai/kelas/ringkasan` | mobile guru | Ringkasan kelas 2 sampai 3 kalimat |
| `POST /ai/anak/{id}/saran-belajar` | mobile guru | 2 sampai 3 saran belajar dari data anak dan rujukan, beserta sumbernya |
| `POST /ai/demo/isi` | demo | Mengisi satu anak dengan data buatan (hanya saat `SATU_DEMO=1`) |

Kirim hasil percobaan:

```json
{ "item_id": "t4-bola", "berhasil": false, "langkah_tercapai": 1, "durasi_ms": 6000 }
```

Jawabannya (contoh asli: kegagalan ketiga berturut-turut pada kata "bola", macet di "o"):

```json
{
  "perubahan": [
    {
      "bunyi": "M",
      "tingkat": 4,
      "berhasil": true,
      "sebelum": 0.963,
      "sesudah": 0.986,
      "label": "sudah_bisa"
    },
    {
      "bunyi": "o",
      "tingkat": 4,
      "berhasil": false,
      "sebelum": 0.0831,
      "sesudah": 0.0631,
      "label": "sedang_dilatih"
    }
  ],
  "tingkat_berhasil": null,
  "berikutnya": {
    "item": {
      "id": "t3-mo",
      "tingkat": 3,
      "teks": "mo",
      "urutan": [
        "M",
        "o"
      ],
      "bantuan_visual": false
    },
    "perkiraan_berhasil": 0.825,
    "alasan": "turun_tingkat",
    "istirahat": true
  }
}
```

- `langkah_tercapai` = jumlah bentuk dalam `urutan` yang sudah dilewati. Kalau gagal, bentuk di posisi itu adalah tempat anak macet.
- `istirahat: true` = tampilkan animasi istirahat (setelah 3 gagal beruntun).
- `tingkat_berhasil` kosong (`null`) selama sesi belum berisi 5 percobaan.
- `streak` = jumlah hari berturut-turut berlatih menurut tanggal WIB; juga ada di jawaban `/peta`.
- Nama anak dikirim hanya ke endpoint teks (`{"nama": "Raka"}`) dan tidak diteruskan ke LLM.

Nilai `alasan`: `zona` (pilihan biasa), `penguatan` (terlalu sering gagal, diberi yang mudah), `lebih_sulit` (terlalu sering berhasil), `lebih_mudah`, `turun_tingkat`, `ganti_bunyi`, `jelajah` (acak 1 dari 10), `ulang_tuntas`.

### Rujukan: buku Kemendikbud, web, dan data anak

Saran belajar (untuk guru) dan cara membantu di laporan orang tua disusun dari dua dasar: data latihan anak (bunyi yang macet, mulai lupa, atau masih lemah) dan paragraf rujukan dari sumber yang dikumpulkan. Gemini hanya boleh menyarankan dari dua dasar itu dan wajib menyebut kode rujukannya; sumber yang dipakai ikut dikirim di field `rujukan` (judul, tautan, halaman). Kalau Gemini menyebut rujukan yang tidak ada, jawabannya ditolak dan dipakai templat yang disusun dari data anak.

Sumber dikumpulkan sekali, sebelum demo, dari laptop yang tersambung internet (server buku Kemendikbud tidak bisa dijangkau dari luar Indonesia):

```bash
python skrip/kumpulkan_pengetahuan.py
```

- Daftar sumber ada di `backend/pengetahuan/sumber.json`: PDF, halaman web, Wikipedia, atau `tata_letak` (ekspor JSON berisi halaman dan elemen teks berposisi, dibaca dari berkas lokal).
- Kolom `bobot` mengatur sumber mana yang didahulukan: buku panduan 1,5, ensiklopedia 0,5. Tambah sumber dengan menyalin satu blok, dan isi kolom `lisensi` (juknis poin d: data harus bebas hak cipta).
- Pengumpul menghormati robots.txt, memberi jeda antar permintaan, dan mengulang kalau dibatasi.
- Hasilnya `backend/satu_ai/data/pengetahuan.json`. Nyalakan ulang backend sesudahnya; `/ai/status` menunjukkan jumlah paragraf rujukan.
- Pencarian rujukan memakai skor kata kunci (BM25) ditambah penanda bunyi dan pembaca, tanpa model tambahan, jadi ringan.

Basis yang ada di repo berisi 525 paragraf: 510 dari *Panduan Guru Pengembangan Wicara bagi Peserta Didik dengan Hambatan Pendengaran* (Aini & Handriani, Kemendikbudristek 2024, halaman cetak 1 sampai 215) dan 15 dari Wikipedia. Buku itu dibaca dari `Pengembangan_Wicara_BG.json` di folder utama repo. Nomor `halaman` di rujukan adalah nomor halaman cetak buku. Buku tersebut berhak cipta Kemendikbudristek, jadi dipakai sebagai kutipan pendidikan dengan menyebut sumber.

### Menyimpan ke database

`PenyimpananMemori` hilang saat server mati. Untuk Postgres, buat kelas dengan dua metode yang sama dan berikan ke `buat_router`:

```python
class PenyimpananPostgres:
    def muat(self, anak_id: str) -> StatusAnak:
        baris = ...  # SELECT status_otak FROM anak WHERE id = anak_id
        return StatusAnak.dari_dict(baris or {})

    def simpan(self, anak_id: str, status: StatusAnak) -> None:
        ...  # UPDATE anak SET status_otak = status.ke_dict()

app.include_router(buat_router(PenyimpananPostgres()))
```

Satu kolom JSON per anak sudah cukup.

## Menjalankan Mata

```bash
cd mata
npm install
npm run siapkan
npm run dev
```

`npm run siapkan` menyalin berkas WASM MediaPipe dan mengunduh model (3,7 MB) ke `public/`, supaya tidak bergantung pada CDN saat demo. Buka `http://localhost:5173`. Kamera hanya jalan di `localhost` atau HTTPS.

Tes dan pemeriksaan tipe:

```bash
npm test
```

```bash
npm run cek-tipe
```

### Halaman uji

1. **Mulai kamera**, lalu **Kalibrasi** sambil diam dengan mulut tertutup.
2. Lihat lima angka (`rahang`, `bulat`, `lebar`, `tekan`, `celah`) sambil membuat tiap bentuk. Keping `a i u o M` menyala kalau aturannya terpenuhi.
3. Tekan **Setel otomatis** dan buat lima bentuk saat diminta; ambang dihitung dari wajahmu dan langsung dipakai. Kalau ada bentuk yang terlalu mirip, halaman menyebut bentuk mana yang perlu diulang. Angka juga bisa diubah sendiri di kotak **Ambang aturan**. Salin hasil akhirnya ke `src/aturan.ts`.
4. **Uji singkat** mencatat berhasil dan jumlah per target, untuk angka di slide.
5. **Sambung ke Otak** menjalankan alur penuh dengan backend.
6. **Tutorial bibir a-z** menggambar bentuk bibir contoh untuk tiap huruf.

### Memakai Mata di aplikasi web

Salin isi `mata/src` kecuali `demo.ts`, dan folder `public/wasm` serta `public/model`.

```ts
import { Mata } from './mata';

const mata = await Mata.buat();                 // memuat model
await mata.mulaiKamera(videoRef.current);       // dari penangan klik
const kalibrasi = await mata.kalibrasi();       // 2 detik wajah netral
if (!kalibrasi.ok) { /* minta ulang: kalibrasi.alasan */ }

// item datang dari Otak: { id, urutan, ... }
const { hasil } = mata.percobaan(item.urutan, (keadaan) => {
  // keadaan.progres, keadaan.petunjuk, keadaan.kemiripan (bilah "Kemiripan"):
  // gambar langsung ke canvas, jangan ke state React
});
const akhir = await hasil;                      // { berhasil, langkah_tercapai, durasi_ms, kemiripan, bintang, poin }
if (akhir) await kirim({ item_id: item.id, ...akhir });
```

## Cara kerja singkat

**Mata.** MediaPipe memberi 52 blendshape per frame; hanya 11 blendshape mulut yang dipakai, masing-masing dikurangi nilai wajah netral anak. Dari situ dihitung lima angka, lalu dibandingkan dengan ambang per bentuk. Bunyi tunggal berhasil kalau bentuk benar dan ada suara selama 0,7 detik. Kata dinilai sebagai urutan bentuk; bibir mengatup di dalam kata tidak perlu bersuara. Wajah hilang menjeda waktu, tidak dihitung gagal. Kemiripan (0 sampai 100%) dihitung dari lima angka yang sama dengan aturan, dengan rata-rata geometris; 100% hanya kalau aturannya lolos. Akurasi di akhir percobaan adalah rata-rata kemiripan selama percobaan. Bintang: berhasil dan akurasi minimal 80% = 3, berhasil = 2, belum berhasil = 1; poin = bintang × 10.

**Otak.** Satu angka penguasaan per bunyi × tingkat (5 × 4). Penguasaan sebuah kata = bunyi terlemahnya. Latihan berikutnya adalah yang perkiraan berhasilnya paling dekat ke 78%, dengan pengaman dari 10 percobaan terakhir. Parameter BKT bukan hasil fit data: dipilih lewat simulasi supaya anak yang berhasil 50% percobaan jarang dicap "sudah bisa" (sekitar 15% waktu) dan anak yang berhasil 80% hampir selalu (sekitar 97%).

**Mulut.** LLM tidak memilih latihan dan tidak menulis angka. Keluarannya ditolak kalau JSON rusak, memuat angka, terlalu panjang, mengubah daftar kata, atau menyebut kata latihan lain; lalu dipakai templat.

### Tutorial bibir a-z

`mata/src/tutorial.ts` berisi bentuk bibir contoh untuk huruf a sampai z, sebagai koordinat 40 titik bibir dengan indeks yang sama dengan MediaPipe (`FACE_LANDMARKS_LIPS`). Bentuknya dibangkitkan dari beberapa parameter (lebar, bukaan, kebulatan), bukan direkam dari wajah, dan arahnya disamakan dengan aturan penilai.

Huruf dikelompokkan menurut bentuk yang terlihat, karena banyak huruf terlihat sama dari luar:

| Bentuk | Huruf | Dinilai |
| --- | --- | --- |
| a, i, u, e, o | a, i, u, e, o | Ya, dari bentuk bibir |
| Bibir menutup (M) | m, b, p | Ya, dari bentuk bibir |
| Gigi dan bibir (F) | f, v | Ya: bibir bawah tergulung ke bawah gigi atas, plus hembusan atau suara |
| Bibir bundar / melebar | w / y | Ya, sebagai bentuk u / i |
| Hembusan (H) | h | Ya, dari mikrofon: desis napas (zero-crossing tinggi), mulut terbuka |
| Desis (S) | s, c, x, z, j | **Sebagian**: gigi hampir rapat dan bibir sedikit terbuka, plus desis di mikrofon |
| Huruf lidah (T) | t, d, n, l, r, k, g, q | **Sebagian**: mulut sedikit terbuka, plus ada bunyi |

"Sebagian" artinya kamera menilai posisi mulut dan suaranya, bukan lidah. Sistem tidak bisa membedakan t dari k, atau l dari r; ketepatan lidah tetap dinilai guru. Item latihan yang mengandung bunyi ini ditandai `dinilai_sebagian: true` di API, dan huruf tutorialnya ditandai `sebagian`.

```ts
import { hurufTutorial, koordinatHuruf, gambarBibir } from './tutorial';

hurufTutorial('b');   // { huruf: 'b', bentuk: 'katup', dinilai: 'M', petunjuk: 'Rapatkan kedua bibir, lalu buka.' }
gambarBibir(kanvas.getContext('2d'), koordinatHuruf('b'));
```

`semuaKoordinat()` mengembalikan semua 26 huruf beserta titiknya, kalau perlu disimpan sebagai JSON.

### Angka simulasi untuk dijawab jujur

Anak tiruan dengan kemampuan tetap (tidak belajar), 200 percobaan, 20 kali ulang:

| Anak tiruan | Peluang berhasil di tingkat 1 / 2 / 3 / 4 | Tingkat berhasil yang tercapai |
| --- | --- | --- |
| Lemah | 55% / 40% / 25% / 15% | 54% |
| Sedang | 85% / 75% / 60% / 45% | 67% |
| Kuat | 97% / 95% / 90% / 85% | 85% |

Pemilih latihan mendekati rentang 70 sampai 85%, tapi tidak bisa mencapainya untuk anak yang di tingkat termudah pun berhasil di bawah 70%. Ini simulasi, bukan data anak sungguhan.

## Yang masih harus dikerjakan

1. Setel ambang bibir dengan wajah anggota tim, lalu di ruangan lomba.
2. Cocokkan `BANK_KATA` di `backend/satu_ai/kurikulum.py` dengan buku guru; daftar sekarang adalah usulan.
3. Ganti `TIPS_PENDAMPING` dengan tips dari buku guru; isinya sekarang pengisi sementara.
4. Isi `.env` dan coba ketiga teks LLM dengan kunci asli.
5. Sambungkan penyimpanan ke database dan tambahkan login di router.
6. Uji kecepatan di laptop sekolah dan HP Android murah.
