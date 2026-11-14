"""Simulasi: apakah pemilih latihan adaptif lebih baik daripada urutan tetap dan acak?

Jalankan dari folder backend (butuh matplotlib untuk grafik):

    python skrip/simulasi_otak.py

Anak tiruan punya "penguasaan asli" per bunyi x tingkat yang tersembunyi dari Otak.
Tiap latihan memberi peluang belajar, lebih kecil kalau tingkat di bawahnya belum
dikuasai (seperti anak yang dipaksa ke kata sebelum bisa bunyinya). Angka anak tiruan
sengaja berbeda dari parameter BKT yang dipakai Otak, supaya Otak tidak "menyontek".

Ini simulasi, bukan data anak sungguhan. Hasilnya ditulis ke data/simulasi/.
"""

from __future__ import annotations

import csv
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from satu_ai import otak  # noqa: E402
from satu_ai.kurikulum import ITEM, Item  # noqa: E402

KELUAR = AKAR.parent / "data" / "simulasi"
PERCOBAAN = 300
ULANG = 50
PER_SESI = 30


@dataclass(frozen=True)
class TipeAnak:
    nama: str
    belajar: float  # peluang menguasai setelah satu latihan yang tepat
    tebak: float  # berhasil padahal belum menguasai
    salah: float  # gagal padahal sudah menguasai


TIPE = (
    TipeAnak("lemah", belajar=0.06, tebak=0.15, salah=0.2),
    TipeAnak("sedang", belajar=0.12, tebak=0.2, salah=0.12),
    TipeAnak("kuat", belajar=0.22, tebak=0.25, salah=0.06),
)


class AnakTiruan:
    def __init__(self, tipe: TipeAnak, rng: random.Random):
        self.tipe, self.rng = tipe, rng
        self.kuasai: set[tuple[str, int]] = set()

    def siap(self, bunyi: str, tingkat: int) -> bool:
        return tingkat == 1 or (bunyi, tingkat - 1) in self.kuasai

    def coba(self, item: Item) -> tuple[bool, int]:
        """Mengembalikan (berhasil, langkah tercapai), lalu mungkin belajar."""
        langkah = 0
        for bunyi in item.urutan:
            kunci = (bunyi, item.tingkat)
            peluang = 1 - self.tipe.salah if kunci in self.kuasai else self.tipe.tebak
            if self.rng.random() >= peluang:
                break
            langkah += 1
        berhasil = langkah == len(item.urutan)
        for bunyi in item.bunyi:
            kunci = (bunyi, item.tingkat)
            if kunci not in self.kuasai:
                laju = self.tipe.belajar * (1.0 if self.siap(*kunci) else 0.2)
                if self.rng.random() < laju:
                    self.kuasai.add(kunci)
        return berhasil, langkah


# ------------------------------------------------------------- cara memilih


def pilih_adaptif(status, sekarang, rng, _keadaan):
    return otak.pilih_berikutnya(status, sekarang, rng).item


URUTAN_KURIKULUM = sorted(ITEM, key=lambda it: (it.level, it.tingkat, ITEM.index(it)))


def pilih_urutan_tetap(_status, _sekarang, _rng, keadaan):
    """Urut kurikulum; pindah setelah 3 berhasil beruntun atau 10 percobaan."""
    return URUTAN_KURIKULUM[min(keadaan["posisi"], len(URUTAN_KURIKULUM) - 1)]


def pilih_acak(_status, _sekarang, rng, _keadaan):
    return rng.choice(ITEM)


CARA = {"Adaptif (SATU)": pilih_adaptif, "Urutan tetap": pilih_urutan_tetap, "Acak": pilih_acak}


def jalankan(tipe: TipeAnak, cara, benih: int) -> dict:
    rng = random.Random(benih)
    anak = AnakTiruan(tipe, rng)
    status = otak.StatusAnak()
    waktu = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
    keadaan = {"posisi": 0, "beruntun": 0, "di_item": 0}
    hasil, gagal_beruntun, frustrasi = [], 0, 0
    for nomor in range(PERCOBAAN):
        if nomor and nomor % PER_SESI == 0:
            waktu += timedelta(days=1)
        item = cara(status, waktu, rng, keadaan)
        berhasil, langkah = anak.coba(item)
        otak.catat_percobaan(status, item, berhasil, langkah, waktu)
        hasil.append(berhasil)
        gagal_beruntun = 0 if berhasil else gagal_beruntun + 1
        frustrasi += gagal_beruntun == 3  # dihitung sekali tiap mencapai 3 gagal beruntun
        keadaan["beruntun"] = keadaan["beruntun"] + 1 if berhasil else 0
        keadaan["di_item"] += 1
        if keadaan["beruntun"] >= 3 or keadaan["di_item"] >= 10:
            keadaan.update(posisi=keadaan["posisi"] + 1, beruntun=0, di_item=0)
        waktu += timedelta(seconds=20)
    blok = [sum(hasil[i : i + 10]) / 10 for i in range(0, PERCOBAAN, 10)]
    return {
        "dikuasai": len(anak.kuasai),
        "berhasil": sum(hasil) / PERCOBAAN,
        "blok_di_zona": sum(0.6 <= b <= 0.9 for b in blok) / len(blok),  # zona 70-85% dengan toleransi
        "frustrasi": frustrasi,
    }


def main() -> None:
    KELUAR.mkdir(parents=True, exist_ok=True)
    baris = []
    for tipe in TIPE:
        for nama_cara, cara in CARA.items():
            hasil = [jalankan(tipe, cara, benih) for benih in range(ULANG)]
            rata = {k: sum(h[k] for h in hasil) / ULANG for k in hasil[0]}
            baris.append({"anak": tipe.nama, "cara": nama_cara, **{k: round(v, 3) for k, v in rata.items()}})
            print(f"{tipe.nama:6} {nama_cara:15} dikuasai={rata['dikuasai']:5.1f}  berhasil={rata['berhasil']:.0%}  "
                  f"blok di zona={rata['blok_di_zona']:.0%}  frustrasi={rata['frustrasi']:.1f}")

    with open(KELUAR / "hasil.csv", "w", newline="", encoding="utf-8") as f:
        tulis = csv.DictWriter(f, fieldnames=list(baris[0]))
        tulis.writeheader()
        tulis.writerows(baris)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib tidak terpasang: hanya hasil.csv yang ditulis")
        return

    warna = {"Adaptif (SATU)": "#2a6fdb", "Urutan tetap": "#9aa5b1", "Acak": "#d9a441"}
    gambar, sumbu = plt.subplots(1, 2, figsize=(11, 4.2))
    lebar = 0.26
    for kolom, (ukuran, judul) in enumerate(
        (
            ("dikuasai", "Bunyi x tingkat yang benar-benar dikuasai\nsetelah 300 percobaan (makin tinggi makin baik)"),
            ("frustrasi", "Kejadian gagal 3 kali beruntun\n(makin rendah makin baik)"),
        )
    ):
        ax = sumbu[kolom]
        for i, nama_cara in enumerate(CARA):
            nilai = [next(b[ukuran] for b in baris if b["anak"] == t.nama and b["cara"] == nama_cara) for t in TIPE]
            posisi = [x + (i - 1) * lebar for x in range(len(TIPE))]
            batang = ax.bar(posisi, nilai, lebar, label=nama_cara, color=warna[nama_cara])
            ax.bar_label(batang, fmt="%.1f", fontsize=8, padding=2)
        ax.set_xticks(range(len(TIPE)), [f"Anak {t.nama}" for t in TIPE])
        ax.set_title(judul, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    sumbu[0].legend(frameon=False, fontsize=9)
    gambar.suptitle("Simulasi pemilih latihan SATU (anak tiruan, 50 ulangan tiap kelompok)", fontsize=11)
    gambar.tight_layout()
    gambar.savefig(KELUAR / "grafik.png", dpi=160)
    print(f"Grafik -> {KELUAR / 'grafik.png'}")


if __name__ == "__main__":
    main()
