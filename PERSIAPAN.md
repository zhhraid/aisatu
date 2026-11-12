# Persiapan lapis AI (tanpa training)

Disusun 10 Nov 2026. Semua isi dokumen ini teks rancangan, bukan kode. Angka di sini adalah titik awal untuk disetel saat lomba, bukan hasil pengukuran.

Dua hal yang perlu kalian periksa sendiri:

- Bank kata di bagian 2 adalah usulan saya. Saya tidak memegang buku guru Aini & Handriani (2024), jadi cocokkan tiap kata dengan buku itu dan buang yang tidak ada.
- Prompt di bagian 4 bisa dianggap panitia sebagai "desain". Tanyakan dulu, atau tulis ulang saat lomba dari ingatan.

---

## 1. Mata: aturan bentuk bibir

### Masukan

- MediaPipe Face Landmarker, dengan keluaran blendshape dinyalakan.
- Tiap blendshape dipakai sebagai **selisih dari netral**: nilai saat ini dikurangi rata-rata nilai selama kalibrasi 2 detik.
- Nilai kiri dan kanan dirata-rata (misalnya `mouthSmileLeft` dan `mouthSmileRight` jadi satu angka "senyum").

### Angka turunan

| Nama | Dihitung dari |
| --- | --- |
| rahang | `jawOpen` |
| bulat | nilai terbesar dari `mouthPucker` dan `mouthFunnel` |
| lebar | nilai terbesar dari rata-rata `mouthSmile` dan rata-rata `mouthStretch` |
| tekan | nilai terbesar dari rata-rata `mouthPress`, `mouthRollLower`, `mouthRollUpper` |
| celah | jarak titik bibir dalam atas (13) ke bawah (14), dibagi tinggi wajah |

### Aturan per bentuk (ambang awal)

| Bentuk | Syarat | Petunjuk untuk anak kalau gagal |
| --- | --- | --- |
| a | rahang ≥ 0,45 dan bulat < 0,30 | "Buka lebih lebar" |
| i | lebar ≥ 0,30 dan rahang < 0,20 dan bulat < 0,15 | "Tarik bibir ke samping" |
| u | bulat ≥ 0,40 dan rahang < 0,20 | "Kerucutkan bibir" |
| o | bulat ≥ 0,30 dan rahang antara 0,20 dan 0,50 | "Bulatkan bibir, buka sedikit" |
| mengatup | celah mendekati nol dan tekan ≥ 0,20 | "Rapatkan bibir" |

Catatan:

- Bentuk mengatup paling sulit dibedakan dari netral, karena saat diam bibir juga tertutup. Untuk suku kata dan kata, nilai mengatup sebagai **tertutup lalu terbuka** (celah nol selama beberapa frame, lalu naik), bukan sebagai pose yang ditahan.
- o dan u dibedakan terutama oleh rahang. Kalau sering tertukar, lebarkan jarak ambang rahangnya.
- é dan ê tidak masuk. Tambahkan hanya kalau lima bentuk ini sudah stabil.

### Kapan satu percobaan dihitung berhasil

| Tingkat | Aturan |
| --- | --- |
| Bunyi tunggal | Syarat bentuk terpenuhi dan ada suara, bersamaan, selama 0,7 detik |
| Suku kata dan kata | Tiap bentuk dalam urutan muncul berurutan, masing-masing minimal 0,15 detik, dan ada suara di sepanjang ucapan |

- Batas waktu satu percobaan: 6 detik. Lewat dari itu dihitung gagal.
- Wajah tidak terdeteksi atau kepala terlalu miring: percobaan dijeda, tidak dihitung gagal.

### Suara

- Ukur kebisingan ruangan 1 detik saat kalibrasi. Ambang suara = kebisingan × 2,5 (setel di ruangan lomba).
- Matikan `autoGainControl` dan `noiseSuppression` pada mikrofon.

### Cara menyetel ambang saat lomba

1. Tampilkan lima angka turunan di layar (mode debug).
2. Tiap anggota tim membuat lima bentuk; catat nilai terendah yang masih terasa benar.
3. Pasang ambang sedikit di bawah nilai terendah itu.
4. Ulangi di ruangan lomba dengan cahaya aslinya.

### Uji singkat untuk slide

5 orang × 5 bentuk × 5 kali = 125 percobaan. Catat berapa yang terbaca benar per bentuk. Sebutkan bahwa pengujinya anggota tim, bukan anak tunarungu.

---

## 2. Bank kata dan urutan bentuk

Hanya bentuk yang terlihat yang dinilai. Konsonan selain m, b, p tidak terlihat di bibir, jadi dilewati. Dua bentuk sama yang berurutan digabung jadi satu.

Singkatan: M = mengatup.

| Kata | Urutan bentuk | Kata | Urutan bentuk |
| --- | --- | --- | --- |
| mama | M, a, M, a | ibu | i, M, u |
| papa | M, a, M, a | api | a, M, i |
| bola | M, o, a | ubi | u, M, i |
| buku | M, u | topi | o, M, i |
| baju | M, a, u | sapu | a, M, u |
| mata | M, a | kaki | a, i |
| pipi | M, i, M, i | kuda | u, a |
| bibi | M, i, M, i | roti | o, i |
| bumi | M, u, M, i | dadu | a, u |
| pita | M, i, a | susu | u |
| palu | M, a, u | gigi | i |
| mobil | M, o, M, i | oma | o, M, a |

Suku kata untuk tingkat 3: ma, mi, mu, mo, ba, bi, bu, bo, pa, pi, pu, po.

Kata dengan huruf e (meja, sepatu, bebek) sengaja tidak dipakai, karena é dan ê tidak dinilai.

---

## 3. Otak: BKT, pemilih latihan, tugas rumah

### Satuan penguasaan

Satu angka penguasaan per **bunyi × tingkat**. MVP memakai 5 bunyi × 4 tingkat = 20 angka per anak.

| Tingkat | Isi | Prasyarat |
| --- | --- | --- |
| 1 | Bunyi tunggal dengan bantuan visual | tidak ada |
| 2 | Bunyi tunggal tanpa bantuan | tingkat 1 bunyi yang sama ≥ 0,6 |
| 3 | Suku kata | tingkat 2 semua bunyi di suku kata itu ≥ 0,6 |
| 4 | Kata 2 suku | tingkat 3 semua bunyi di kata itu ≥ 0,6 |

### Parameter awal

Nilai ini bukan hasil fit data. Sebutkan begitu saat presentasi. Diperbarui 11 Nov setelah simulasi: tebakan pertama saya membuat anak yang hanya berhasil 40% percobaan tetap dicap "sudah bisa".

| Parameter | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- |
| Peluang awal menguasai | 0,30 | 0,20 | 0,15 | 0,10 |
| Peluang belajar per percobaan | 0,05 | 0,05 | 0,05 | 0,05 |
| Peluang berhasil padahal belum menguasai (tebak) | 0,35 | 0,35 | 0,35 | 0,35 |
| Peluang gagal padahal sudah menguasai (salah ucap) | 0,10 | 0,10 | 0,10 | 0,10 |

Dengan angka ini, di simulasi anak yang berhasil 50% percobaan dicap "sudah bisa" hanya sekitar 15% waktu, dan anak yang berhasil 80% dicap begitu sekitar 97% waktu. Di tingkat 1, tiga kali berhasil beruntun membuat bunyi jadi "sudah bisa" dan empat kali membuatnya tuntas.

### Rumus update setelah satu percobaan

P = penguasaan sebelum percobaan, t = tebak, s = salah ucap, b = belajar.

- Kalau berhasil: P' = P(1 − s) / [P(1 − s) + (1 − P)t]
- Kalau gagal: P' = P·s / [P·s + (1 − P)(1 − t)]
- Lalu: P baru = P' + (1 − P')·b

### Bunyi mana yang diperbarui pada kata

- Kata berhasil: semua bunyi di kata itu diperbarui sebagai berhasil, di tingkat kata itu.
- Kata gagal: bunyi yang sudah lewat diperbarui sebagai berhasil, bunyi tempat anak macet diperbarui sebagai gagal, bunyi sesudahnya tidak diubah.

### Memilih latihan berikutnya

1. Kumpulkan kandidat: bunyi × tingkat yang prasyaratnya terpenuhi dan penguasaannya masih di bawah 0,95. Penguasaan sebuah kata = bunyi terlemahnya.
2. Untuk tiap kandidat hitung perkiraan berhasil: P(1 − s) + (1 − P)t.
3. Pilih kandidat yang perkiraannya paling dekat ke 0,78 (tengah rentang 70–85%).
4. Satu dari sepuluh kali, pilih kandidat lain secara acak supaya tidak terpaku.
5. Jangan beri latihan yang sama lebih dari 3 kali berturut-turut kalau ada kandidat lain.

### Pengaman

- Tingkat berhasil dihitung dari **10 percobaan terakhir** di sesi itu, minimal 5 percobaan. Di bawah 70%: beri latihan penguatan, yaitu yang perkiraan berhasilnya 70% ke atas, termasuk yang sudah tuntas. Di atas 85%: pilih hanya dari tingkat tertinggi yang terbuka.
- 3 gagal beruntun: turun satu tingkat pada bunyi itu dan tampilkan animasi istirahat.
- Server tidak terjangkau: browser pakai aturan cadangan (3 berhasil naik, 2 gagal turun) dan mengirim hasil saat koneksi kembali.

### Lupa dan tugas rumah

- Penguasaan turun pelan menuju peluang awalnya: P(sekarang) = awal + (P − awal) × 0,5^(hari sejak latihan terakhir / 30).
- Waktu paruh 30 hari adalah asumsi. Dengan 7 hari, anak yang sudah tuntas terlihat mundur dalam seminggu.
- Yang pernah tuntas baru diulang setelah turun di bawah 0,85.
- Usulan tugas rumah: 3 latihan yang sudah pernah dilatih, diurutkan dari bunyi yang paling banyak lupa atau paling lemah; kalau belum cukup, diisi materi baru. Hanya dari tingkat yang pernah dicapai anak. Otak yang memilih; LLM hanya menulis alasannya.

### Label untuk orang tua dan warna untuk guru

| Penguasaan | Orang tua | Warna guru |
| --- | --- | --- |
| ≥ 0,85 | Sudah bisa | hijau |
| 0,50 – 0,85 | Hampir bisa | kuning |
| < 0,50 | Sedang dilatih | merah |

### Skenario demo

1. Anak baru mulai di "a" tingkat 1, berhasil 3 kali: titik jadi hijau dan peta guru ikut berubah.
2. Anak dengan profil demo "menengah" berlatih di tingkat 2; sengaja gagal 3 kali beruntun: sistem turun satu tingkat dan animasi istirahat muncul. Setelah satu kegagalan sistem bisa berpindah bunyi, jadi tiga kegagalan itu tidak selalu di bunyi yang sama.
3. Guru membuka usulan tugas, menyetujui, lalu halaman orang tua menampilkan 3 latihan.

---

## 4. Mulut: prompt dan pagar

### Aturan umum

- LLM tidak memilih kata dan tidak menulis angka. Kata datang dari Otak; angka disisipkan server ke templat.
- Keluaran wajib JSON sesuai skema. Server menolak keluaran yang JSON-nya rusak, memuat kata di luar bank kata, memuat angka, atau melebihi batas panjang.
- Kalau ditolak, timeout 8 detik, atau kuota habis: pakai templat cadangan.
- Nama anak tidak dikirim ke LLM. Kirim penanda (misalnya "ANAK"), lalu server menggantinya dengan nama panggilan.

### Tugas A: alasan usulan tugas (untuk guru)

Masukan: daftar 3 kata pilihan Otak, dan untuk tiap kata: bunyi yang lemah, label penguasaan, hari sejak terakhir dilatih.

Instruksi:

> Kamu membantu guru bina wicara di SLB. Untuk tiap kata yang diberikan, tulis satu kalimat alasan mengapa kata itu cocok dilatih hari ini, berdasarkan data yang diberikan saja. Pakai bahasa Indonesia sederhana. Jangan menyebut angka. Jangan menambah kata latihan lain. Jangan memberi diagnosis atau janji hasil. Sebut anak sebagai ANAK.

Keluaran: `{"tugas": [{"kata": "...", "alasan": "..."}]}` dengan tepat 3 butir, alasan maksimal 20 kata.

Templat cadangan: "Kata {kata} dipilih karena bunyi {bunyi} {label} dan terakhir dilatih {hari} hari lalu."

### Tugas B: ringkasan kelas (untuk guru)

Masukan: per anak, bunyi yang macet (dari aturan sederhana) dan bunyi yang baru naik.

Instruksi:

> Tulis ringkasan kelas dalam 2 sampai 3 kalimat untuk guru: siapa yang perlu perhatian dan di bunyi apa, lalu satu hal yang membaik. Pakai hanya data yang diberikan. Jangan menyebut angka. Jangan memberi saran medis.

Keluaran: `{"ringkasan": "..."}`, maksimal 60 kata.

Templat cadangan: "{jumlah} anak perlu perhatian: {daftar anak dan bunyi}. Yang membaik minggu ini: {daftar}."

### Tugas C: laporan mingguan (untuk orang tua)

Masukan: bunyi berlabel "Sudah bisa", bunyi "Hampir bisa", bunyi "Sedang dilatih", jumlah hari latihan minggu ini, dan 1 tips dari buku guru yang dipilih server.

Instruksi:

> Tulis laporan singkat untuk orang tua anak tunarungu. Nada hangat dan apa adanya, tanpa istilah teknis. Tiga bagian: yang sudah bisa, yang sedang dilatih, cara membantu di rumah. Untuk cara membantu, pakai tips yang diberikan dengan kata-katamu sendiri; jangan menambah tips lain. Jangan menyebut angka, jangan membandingkan dengan anak lain, jangan menjanjikan hasil. Sebut anak sebagai ANAK.

Keluaran: `{"sudah_bisa": "...", "sedang_dilatih": "...", "cara_membantu": "..."}`, tiap bagian maksimal 30 kata.

Templat cadangan: "ANAK sudah bisa bunyi {daftar}. Minggu ini ANAK sedang berlatih bunyi {daftar}. Di rumah: {tips}."

### Cek sebelum lomba

- Coba ketiga tugas di antarmuka chat penyedia LLM dengan 5 data karangan, dan lihat apakah keluarannya patuh.
- Catat model, batas kuota gratis per menit dan per hari.

---

## 5. Yang masih harus kalian lakukan

1. Kirim pertanyaan ke panitia: project lama, durasi presentasi, kriteria penilaian, dan apakah dokumen seperti ini dianggap desain.
2. Cocokkan bank kata dengan buku guru.
3. Unduh file model Face Landmarker dan cek kunci API LLM.
4. Sepakati dengan fullstack dan mobile: nama bunyi (a, i, u, o, M), nomor tingkat (1–4), dan tiga label penguasaan.
