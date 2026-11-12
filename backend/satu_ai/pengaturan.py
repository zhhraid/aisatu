"""Membaca berkas .env di folder backend dan mencatat keadaannya.

Dibaca sendiri (bukan lewat --env-file) supaya dua masalah umum di Windows tidak
membuat pengaturan diam-diam kosong: berkas tersimpan dengan BOM atau sebagai
UTF-16 oleh Notepad, dan berkas bernama .env.txt.
"""

import os
from pathlib import Path

# Dibaca endpoint /ai/status supaya masalah terlihat dari browser.
STATUS = {"berkas_env": "tidak dimuat"}


def urai(teks: str) -> dict[str, str]:
    """Mengurai baris NAMA=nilai. Baris kosong dan komentar (#) dilewati."""
    hasil: dict[str, str] = {}
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        nama, nilai = baris.removeprefix("export ").split("=", 1)
        nilai = nilai.strip()
        if len(nilai) >= 2 and nilai[0] == nilai[-1] and nilai[0] in "\"'":
            nilai = nilai[1:-1]
        hasil[nama.strip()] = nilai
    return hasil


def _baca(jalur: Path) -> str:
    data = jalur.read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def muat_env(folder: Path) -> str:
    """Memuat folder/.env ke environment. Variabel yang sudah ada tidak ditimpa.

    Mengembalikan keterangan singkat, yang juga disimpan di STATUS["berkas_env"].
    """
    jalur = folder / ".env"
    if not jalur.exists():
        if (folder / ".env.txt").exists():
            keterangan = "tidak ada, tapi ada .env.txt: ganti namanya jadi .env"
        elif (folder.parent / ".env").exists():
            keterangan = f"salah tempat: ada di {folder.parent}, pindahkan ke {folder}"
        else:
            keterangan = f"tidak ada di {folder}: salin .env.example jadi .env di folder itu"
    else:
        try:
            isi = urai(_baca(jalur))
        except (OSError, UnicodeError) as galat:
            keterangan = f"tidak terbaca ({type(galat).__name__}): simpan ulang sebagai UTF-8"
        else:
            for nama, nilai in isi.items():
                if nilai and not os.environ.get(nama):
                    os.environ[nama] = nilai
            keterangan = f"terbaca, {len(isi)} baris pengaturan"
    STATUS["berkas_env"] = keterangan
    return keterangan
