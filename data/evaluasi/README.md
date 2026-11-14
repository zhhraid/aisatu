# Evaluasi penilai bentuk bibir (Mata)

## Uji wajah asli, 14 November 2026

- **Penguji:** 1 anggota tim (dewasa, pendengaran normal), laptop, cahaya ruangan.
- **Cara:** halaman uji Mata, satu rekaman 2 detik per bentuk, tebakan = suara terbanyak dari tiap frame.
- **Jumlah:** 7 rekaman (satu per bentuk). Terlalu sedikit untuk angka akurasi yang kuat.

| Target | Tebakan aturan | Benar |
| --- | --- | --- |
| a | a | Ya |
| i | e | Tidak |
| u | u | Ya |
| o | o | Ya |
| m/b/p | m/b/p | Ya |
| e | e | Ya |
| f/v | m/b/p | Tidak |

**Aturan bawaan: 5 dari 7 benar.**

Model personal tidak bisa dinilai dari uji ini: tabelnya ikut mencatat model yang belum layak
dipakai (akurasi validasi di bawah 80%). Alat ukurnya sudah diperbaiki sehingga hanya model yang
sedang dipakai yang dinilai.

## Perubahan dari uji ini

Kedua kesalahan berada di batas antar-bentuk yang saya tebak sebelum ada data wajah:

| Kesalahan | Penyebab | Perubahan |
| --- | --- | --- |
| "i" dikira "e" | Rahang saat "i" biasa sedikit lebih terbuka dari batas | Batas rahang i/e 0,12 → 0,15 |
| "f" dikira bibir rapat | Bibir bawah tergulung lebih sedikit dari batas | Batas gulung f 0,20 → 0,12 |

Pemeriksa tumpang tindih (`cekTumpang`) tetap kosong: tidak ada bentuk bibir yang lolos sebagai
dua bunyi dengan batas baru. Perubahan ini belum diuji ulang dengan wajah asli.

## Cara menyebutnya di presentasi

> "Penilai bentuk bibir diuji pada satu anggota tim: 5 dari 7 bentuk dikenali dengan aturan
> bawaan. Dua batas yang keliru sudah disetel dari hasil itu. Untuk tiap anak, SATU melatih
> model bibir personal dari 10 detik contoh wajahnya, dan model hanya dipakai bila akurasi
> validasinya minimal 80%. Belum diuji pada anak tunarungu."

Jangan sebut "akurasi 71%" tanpa keterangan jumlah dan siapa pengujinya.

## Uji di aplikasi tim, 14 November 2026

Saat penilai dipasang di layar "Mari Berlatih", bentuk "u" dan "o" sulit lolos walau bibir sudah
mengerucut (contoh: kemiripan 41% dengan petunjuk "kerucutkan bibir"). Penyebabnya, kebulatan
hanya dibaca dari `mouthPucker` dan `mouthFunnel` MediaPipe, yang sering kecil pada kamera laptop.

Perbaikan:

- Kebulatan kini juga dibaca dari **penyempitan mulut**: jarak sudut bibir kiri-kanan dibagi
  lebar wajah, dibanding saat netral. Penyempitan 20% setara kebulatan 0,4.
- Penyempitan yang wajar karena rahang terbuka ("a") dikurangi, supaya "a" tidak terbaca membulat.
- Batas kebulatan diturunkan: "u" 0,35 → 0,20, "o" 0,25 → 0,15, dan batas "tidak membulat" untuk a, e, m/b/p, f ikut 0,25 → 0,15 (batas bersama, `cekTumpang` tetap bersih). Pengukuran tim dengan `?debug` mencatat `mouthPucker` hanya 0,08 untuk "u" yang benar; batas tidak diturunkan sampai 0,06 karena wajah diam pun bergoyang sekitar 0,05.

Belum diuji ulang dengan wajah asli. Untuk tiap anak, Setel otomatis dan model personal tetap cara
paling andal menyesuaikan penilai dengan wajahnya.
