# Model dan teknik AI/ML di SATU

Daftar ini menjelaskan setiap fitur AI/ML SATU: model atau teknik apa yang dipakai, siapa yang
melatihnya, dan di mana berjalan. Dipakai untuk presentasi dan untuk tim.

## Ringkasan

| Jenis | Yang dipakai | Dilatih oleh |
| --- | --- | --- |
| Model ML jadi | MediaPipe Face Landmarker (penglihatan) | Google |
| Model bahasa besar (LLM) | Gemini 3.5 Flash-Lite | Google |
| **Model ML yang dilatih SATU** | **Classifier nearest centroid per anak** (model bibir personal) | **SATU, di browser, dari wajah tiap anak** |
| Model peluang | Bayesian Knowledge Tracing (BKT) | Parameter dipilih tim lewat simulasi |
| Temu kembali informasi | BM25 + penanda bunyi dan pembaca (RAG) | Tidak dilatih |
| Pengolahan sinyal | Energi suara (RMS), zero-crossing rate | Tidak dilatih |
| Algoritma dan aturan | Pemilih latihan zona belajar, level, deteksi lelah, pagar LLM | Ditulis tim, sebagian disetel lewat simulasi dan uji wajah |

Tidak ada model yang dilatih sebelum hari H. Model bibir personal dilatih saat aplikasi berjalan,
dari contoh wajah anak itu sendiri.

## Mata: menilai bibir dan suara (di browser, video tidak keluar perangkat)

| Fitur | Model / teknik | Keterangan | Berkas |
| --- | --- | --- | --- |
| Deteksi wajah, 478 titik wajah, 52 gerakan otot wajah (blendshape) | **MediaPipe Face Landmarker** (jaringan saraf, model jadi `float16`, 3,7 MB) | Berjalan di browser lewat WebAssembly, GPU bila ada | `mata/src/mata.ts` |
| Enam ciri bibir: rahang, bulat, lebar, tekan, celah, gulung | Rekayasa ciri dari 11 blendshape mulut dan titik bibir, **dikurangi wajah netral anak** | Kalibrasi netral: rata-rata 2 detik wajah diam | `mata/src/fitur.ts`, `kalibrasi.ts` |
| Penilai bentuk bibir bawaan | **Aturan ambang** dengan batas bersama antar-bentuk | Dijamin satu bentuk tidak lolos sebagai dua bunyi (`cekTumpang`); dua batas disetel dari uji wajah asli | `mata/src/aturan.ts` |
| Setel otomatis | **Penyetelan ambang dari contoh** (median tiap bentuk, batas di tengah antar-bentuk) | 7 bentuk × 2 detik dari anak | `mata/src/aturan.ts` |
| **Model bibir personal** | **Classifier nearest centroid** dengan normalisasi sebaran dalam-kelas dan peluang softmax dari jarak | Dilatih di browser dari contoh Setel otomatis; diukur dengan **validasi silang leave-one-out**; dipakai hanya bila akurasi ≥ 80% | `mata/src/model.ts` |
| Model yang terus belajar | **Pembaruan daring (online learning)**: titik tengah digeser ke contoh baru, bobot minimal 1/60 | Hanya dari percobaan berhasil yang sudah diyakini model (≥ 80%) dan dekat dengan bentuk yang dikenal (self-training berpagar) | `mata/src/model.ts` |
| Ada suara | **Energi suara (RMS)** dengan ambang dari kebisingan ruangan | Diukur 1 detik saat kalibrasi | `mata/src/suara.ts` |
| Hembusan (h) dan desis (s, c, z, j) | **Zero-crossing rate** + energi: derau vs nada | Suara bernada bergetar pelan, desis bergetar cepat dan acak | `mata/src/suara.ts` |
| Penilai kata | **Pencocokan urutan**: tiap bentuk harus muncul berurutan dan ditahan sebentar | Bibir rapat dan huruf lidah boleh singkat; wajah hilang menjeda waktu | `mata/src/percobaan.ts` |
| Kemiripan, bintang, poin | **Rata-rata geometris** kedekatan tiap syarat, atau peluang dari model personal | 100% hanya bila bentuk lolos | `mata/src/aturan.ts`, `percobaan.ts` |
| Huruf lidah (dinilai sebagian) | Aturan posisi mulut + jenis suara | Lidah tidak terlihat kamera; t dan k tidak bisa dibedakan | `mata/src/aturan.ts` |
| Uji akurasi | **Suara terbanyak** per rekaman + **tabel kebingungan** | Membandingkan aturan dan model personal | `mata/src/evaluasi.ts` |

## Otak: personalisasi dan level (backend Python)

| Fitur | Model / teknik | Keterangan | Berkas |
| --- | --- | --- | --- |
| Penguasaan per bunyi × tingkat | **Bayesian Knowledge Tracing**: model Markov tersembunyi dua keadaan (menguasai / belum) dengan empat parameter (awal, belajar, tebak, salah) | Parameter dipilih lewat simulasi supaya anak yang berhasil 50% jarang dicap "sudah bisa" | `backend/satu_ai/bkt.py`, `kurikulum.py` |
| Lupa | **Peluruhan eksponensial** dengan paruh 30 hari menuju nilai awal | Gagasan dari half-life regression (Settles & Meeder 2016); paruh adalah asumsi | `backend/satu_ai/bkt.py` |
| Pemilih latihan berikutnya | **Kebijakan zona belajar**: latihan dengan perkiraan berhasil (dari BKT) paling dekat ke 78%, **eksplorasi acak 10% (ε-greedy)** | Ditambah aturan: turun tingkat setelah 3 gagal, latihan penguatan diselingi, hanya dari level terbuka. Disetel lewat simulasi | `backend/satu_ai/otak.py` |
| Peta Level 1–6 | **Agregasi penguasaan BKT** per kelompok bunyi | Level berikutnya terbuka di 40% (dari simulasi) | `backend/satu_ai/otak.py` |
| Bunyi macet, mulai lupa, masih lemah | **Aturan di atas BKT** dan jumlah percobaan | Dasar saran belajar dan agent | `backend/satu_ai/otak.py` |
| Usulan tugas rumah | **Pemeringkatan** dari besar lupa dan lemahnya penguasaan | Tidak melampaui tingkat yang sudah dicapai anak | `backend/satu_ai/otak.py` |
| Deteksi lelah | **Aturan pola sesi**: lama sesi, median waktu menjawab (makin lambat 1,6×), tingkat berhasil turun 30 poin | Angka awal, belum divalidasi pada anak | `backend/satu_ai/otak.py` |
| Riwayat dan tren | Agregasi harian dan perbandingan minggu ini vs sebelumnya | Untuk grafik guru dan agent | `backend/satu_ai/otak.py` |
| Bukti personalisasi | **Simulasi Monte Carlo** dengan anak tiruan berkeadaan tersembunyi (450 anak tiruan) | Membandingkan adaptif, urutan tetap, acak | `backend/skrip/simulasi_otak.py`, `data/simulasi/` |

## Mulut: teks untuk guru dan orang tua (backend Python)

| Fitur | Model / teknik | Dasar data | Berkas |
| --- | --- | --- | --- |
| Alasan usulan tugas | **Gemini** (LLM), keluaran JSON | Data anak dari Otak | `backend/satu_ai/mulut.py` |
| Ringkasan kelas | **Gemini** | Bunyi macet dan naik tiap anak | `backend/satu_ai/mulut.py` |
| Laporan mingguan orang tua | **Gemini + RAG** | Data anak + rujukan buku | `backend/satu_ai/mulut.py` |
| Saran pembelajaran untuk guru | **Gemini + RAG** | Fokus belajar dari Otak + rujukan buku | `backend/satu_ai/mulut.py` |
| **Agent tanya progres** | **Gemini + RAG**, satu panggilan dengan konteks data anak | Level, penguasaan per tahap, kelemahan, tren, streak, rujukan | `backend/satu_ai/mulut.py`, `api.py` |
| Pencarian rujukan (RAG) | **BM25** + bobot penanda bunyi dan pembaca + bobot sumber | 525 paragraf: buku *Panduan Guru Pengembangan Wicara* (Kemendikbudristek 2024) dan Wikipedia | `backend/satu_ai/pengetahuan.py` |
| Pengumpul rujukan (scraping) | Pengunduh dengan robots.txt dan jeda, pembaca PDF (pypdf), HTML, Wikipedia, dan tata letak JSON; pemotong paragraf; penanda bunyi | Daftar sumber bisa ditambah | `backend/skrip/kumpulkan_pengetahuan.py` |
| Pagar LLM | **Validasi aturan**: JSON, panjang, tanpa persen, rujukan harus ada, kode internal dibuang; nama anak disamarkan sebelum dikirim | Gagal → templat dari data | `backend/satu_ai/mulut.py`, `llm.py` |

## Alur satu latihan

1. **Mata** membaca wajah (MediaPipe) → enam ciri bibir → dinilai oleh model personal (atau aturan) + suara → hasil percobaan.
2. **Otak** memperbarui penguasaan (BKT) → cek lelah → memilih latihan berikutnya dari level yang terbuka.
3. **Mulut** memakai data Otak + rujukan buku (RAG) → Gemini menulis saran, laporan, dan jawaban agent → dicek pagar.

## Batas yang disebut jujur

- Penilai bibir baru diuji pada 1 orang dewasa (7 rekaman, 5 benar); belum pada anak tunarungu.
- Parameter BKT, lupa, dan lelah dipilih lewat simulasi atau asumsi, bukan dari data anak.
- Huruf lidah hanya dinilai sebagian (posisi mulut dan suara).
- Gemini bisa salah; karena itu jawabannya dipagari dan berdasar data serta rujukan.
