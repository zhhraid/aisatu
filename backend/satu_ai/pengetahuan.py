"""Basis pengetahuan: paragraf rujukan dari buku Kemendikbud, web, dan Wikipedia.

Isinya dibuat oleh skrip/kumpulkan_pengetahuan.py dan disimpan di
satu_ai/data/pengetahuan.json. Modul ini hanya membaca dan mencari, tanpa model
tambahan: skor BM25 dari kata kunci, ditambah bobot untuk paragraf yang ditandai
membahas bunyi yang sedang lemah dan ditujukan ke pembaca yang sama.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

BERKAS = Path(__file__).resolve().parent / "data" / "pengetahuan.json"

# Kata yang terlalu umum untuk membedakan paragraf.
_KATA_UMUM = set(
    "yang dan di ke dari untuk dengan pada adalah ini itu dalam atau juga akan oleh "
    "tidak sebagai dapat agar karena bagi para lebih secara serta saat telah sudah "
    "ada suatu setiap tersebut harus bisa hal jika maka namun antara".split()
)

# Kata kunci penanda bunyi, dipakai pengumpul (penandaan) dan pencari (kueri).
KATA_BUNYI: dict[str, list[str]] = {
    "a": ["vokal a", "bunyi a", "/a/", "membuka mulut", "mulut terbuka"],
    "i": ["vokal i", "bunyi i", "/i/", "bibir melebar", "bibir ditarik"],
    "u": ["vokal u", "bunyi u", "/u/", "bibir maju", "mengerucut", "monyong"],
    "o": ["vokal o", "bunyi o", "/o/", "bibir bulat", "membulat"],
    "M": ["bilabial", "dwibibir", "kedua bibir", "bibir rapat", "merapatkan bibir",
          "bunyi m", "bunyi b", "bunyi p", "/m/", "/b/", "/p/"],
    "e": ["vokal e", "bunyi e", "/e/", "/é/", "/ê/", "pepet", "taling"],
    "F": ["labiodental", "bibir bawah", "gigi atas", "bunyi f", "bunyi v", "/f/", "/v/"],
    "H": ["glotal", "hembusan", "embusan", "napas", "bunyi h", "/h/", "tisu", "lilin"],
}

KATA_PEMBACA: dict[str, list[str]] = {
    "orang_tua": ["orang tua", "keluarga", "di rumah", "mendampingi", "ayah", "ibu bapak"],
    "guru": ["guru", "pembelajaran", "kegiatan belajar", "di kelas", "asesmen", "evaluasi"],
}


def token(teks: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]{3,}", teks.lower()) if t not in _KATA_UMUM]


def tandai_bunyi(teks: str) -> list[str]:
    kecil = teks.lower()
    return [b for b, kata in KATA_BUNYI.items() if any(k in kecil for k in kata)]


def tandai_pembaca(teks: str) -> list[str]:
    kecil = teks.lower()
    return [p for p, kata in KATA_PEMBACA.items() if any(k in kecil for k in kata)]


class Pengetahuan:
    def __init__(self, data: dict):
        self.sumber: dict[str, dict] = {s["id"]: s for s in data.get("sumber", [])}
        self.paragraf: list[dict] = data.get("paragraf", [])
        self._tok = [Counter(token(p["teks"])) for p in self.paragraf]
        self._panjang = [sum(c.values()) for c in self._tok]
        self._rata = (sum(self._panjang) / len(self._panjang)) if self._panjang else 1
        df: Counter = Counter()
        for c in self._tok:
            df.update(c.keys())
        n = len(self.paragraf)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def __len__(self) -> int:
        return len(self.paragraf)

    def _bm25(self, i: int, kueri: list[str]) -> float:
        k1, b = 1.4, 0.75
        c, panjang = self._tok[i], self._panjang[i]
        skor = 0.0
        for t in kueri:
            f = c.get(t, 0)
            if f:
                skor += self._idf.get(t, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * panjang / self._rata))
        return skor

    def cari(self, bunyi: list[str], pembaca: str, k: int = 3) -> list[dict]:
        """Paragraf paling relevan untuk bunyi yang lemah dan pembaca tertentu.

        Paragraf yang skornya di bawah seperempat skor terbaik dibuang, supaya yang
        dikirim ke LLM hanya rujukan yang memang relevan, bukan pengisi.
        """
        if not self.paragraf:
            return []
        frasa = [f for b in bunyi for f in KATA_BUNYI.get(b, [])] + KATA_PEMBACA.get(pembaca, [])
        kueri = token(" ".join(frasa) + " wicara bicara latihan artikulasi")
        nilai = []
        for i, p in enumerate(self.paragraf):
            skor = self._bm25(i, kueri)
            tanda = set(p.get("bunyi", []))
            skor += 2.0 * len(tanda & set(bunyi))
            if tanda and not tanda & set(bunyi):
                skor -= 1.5  # membahas bunyi lain
            skor += 1.5 if pembaca in p.get("pembaca", []) else 0
            # Bobot sumber dari sumber.json: buku panduan lebih dipercaya daripada ensiklopedia.
            skor *= self.sumber.get(p["sumber"], {}).get("bobot") or 1.0
            if skor > 0:
                nilai.append((skor, i))
        nilai.sort(reverse=True)

        hasil: list[dict] = []
        terbaik = nilai[0][0] if nilai else 0
        for skor, i in nilai:
            if skor < 0.25 * terbaik:
                break
            p = self.paragraf[i]
            s = self.sumber.get(p["sumber"], {})
            hasil.append(
                {
                    "teks": p["teks"],
                    "judul": s.get("judul", p["sumber"]),
                    "url": s.get("url"),
                    "halaman": p.get("halaman"),
                    "lisensi": s.get("lisensi"),
                }
            )
            if len(hasil) >= k:
                break
        return hasil


@lru_cache(maxsize=1)
def muat(berkas: Path = BERKAS) -> Pengetahuan:
    """Basis pengetahuan dari berkas; kosong kalau berkasnya belum dibuat."""
    if not berkas.exists():
        return Pengetahuan({})
    return Pengetahuan(json.loads(berkas.read_text(encoding="utf-8")))
