"""Mengumpulkan paragraf rujukan dari buku Kemendikbud, halaman web, dan Wikipedia.

Jalankan dari folder backend, sekali sebelum demo (butuh internet):

    python skrip/kumpulkan_pengetahuan.py

Daftar sumber ada di pengetahuan/sumber.json dan boleh ditambah. Hasilnya ditulis ke
satu_ai/data/pengetahuan.json, yang dibaca backend saat menyusun saran. Berkas yang
diunduh disimpan di pengetahuan/mentah/ supaya tidak diunduh ulang.

Aturan yang dijaga:
- Hanya sumber di sumber.json yang diambil, dan robots.txt situs dihormati.
- Permintaan diberi jeda, dan diulang dengan jeda lebih lama kalau dibatasi (429).
- Juknis poin d: pakai data yang bebas hak cipta. Isi kolom "lisensi" tiap sumber.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from satu_ai.pengetahuan import tandai_bunyi, tandai_pembaca  # noqa: E402

FOLDER = AKAR / "pengetahuan"
TUJUAN = AKAR / "satu_ai" / "data" / "pengetahuan.json"
AGEN = "SATU-pengumpul/0.1 (proyek hackathon pendidikan; menghormati robots.txt)"

# Paragraf disimpan hanya kalau membahas topik yang relevan.
KATA_RELEVAN = re.compile(
    r"wicara|bicara|berbicara|artikulasi|ucap|lafal|vokal|konsonan|bibir|mulut|"
    r"pendengaran|rungu|tuli|orang tua|keluarga|latihan|membaca ujaran|isyarat",
    re.IGNORECASE,
)
MIN_KATA, MAKS_KATA = 30, 140


# ------------------------------------------------------------------ unduh


def unduh(url: str, jeda: float) -> bytes:
    nama = hashlib.sha1(url.encode()).hexdigest()[:16]
    simpanan = FOLDER / "mentah" / nama
    if simpanan.exists():
        return simpanan.read_bytes()
    for coba in range(5):
        time.sleep(jeda * (2**coba if coba else 1))
        permintaan = urllib.request.Request(url, headers={"User-Agent": AGEN})
        try:
            with urllib.request.urlopen(permintaan, timeout=120) as jawab:
                data = jawab.read()
            simpanan.parent.mkdir(parents=True, exist_ok=True)
            simpanan.write_bytes(data)
            return data
        except urllib.error.HTTPError as galat:
            if galat.code not in (429, 500, 502, 503, 504):
                raise
            print(f"    dibatasi atau gangguan (HTTP {galat.code}), mencoba lagi")
    raise RuntimeError(f"gagal mengunduh setelah 5 kali: {url}")


def boleh_diambil(url: str) -> bool:
    bagian = urllib.parse.urlsplit(url)
    robot = urllib.robotparser.RobotFileParser()
    robot.set_url(f"{bagian.scheme}://{bagian.netloc}/robots.txt")
    try:
        robot.read()
    except Exception:
        return True  # robots.txt tidak bisa dibaca: dianggap tidak ada larangan
    return robot.can_fetch(AGEN, url)


# --------------------------------------------------------------- ambil teks


class _TeksHtml(HTMLParser):
    """Teks paragraf dari HTML, tanpa skrip, gaya, navigasi, dan kaki halaman."""

    _ABAIKAN = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript"}
    _BLOK = {"p", "li", "h1", "h2", "h3", "h4", "div", "br", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.dalam_abaikan = 0
        self.bagian: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._ABAIKAN:
            self.dalam_abaikan += 1
        elif tag in self._BLOK:
            self.bagian.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ABAIKAN and self.dalam_abaikan:
            self.dalam_abaikan -= 1
        elif tag in self._BLOK:
            self.bagian.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.dalam_abaikan:
            self.bagian.append(data)


def teks_html(data: bytes) -> list[tuple[str, int | None]]:
    pengurai = _TeksHtml()
    pengurai.feed(data.decode("utf-8", errors="replace"))
    return [("".join(pengurai.bagian), None)]


def teks_pdf(data: bytes, halaman: list[int] | None) -> list[tuple[str, int | None]]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf belum terpasang: pip install -r requirements.txt")
    import io

    pembaca = PdfReader(io.BytesIO(data))
    awal, akhir = (halaman or [1, len(pembaca.pages)])
    hasil = []
    for nomor in range(max(awal, 1), min(akhir, len(pembaca.pages)) + 1):
        teks = pembaca.pages[nomor - 1].extract_text() or ""
        hasil.append((teks, nomor))
    return hasil


def teks_wikipedia(judul: str, bahasa: str, jeda: float) -> tuple[list[tuple[str, None]], str]:
    url = (
        f"https://{bahasa}.wikipedia.org/w/api.php?action=query&format=json&prop=extracts|info"
        f"&inprop=url&explaintext=1&redirects=1&titles={urllib.parse.quote(judul)}"
    )
    data = json.loads(unduh(url, jeda))
    halaman = next(iter(data["query"]["pages"].values()))
    # Judul bagian ("== Penyebab ==") jadi pemisah paragraf.
    teks = re.sub(r"\n=+[^=\n]+=+\n", "\n\n", halaman.get("extract", ""))
    return [(teks, None)], halaman.get("fullurl", url)


# Huruf gabungan (ligatur) yang tersimpan sebagai simbol lain saat PDF diekspor.
LIGATUR = {"ȑ": "fi", "ȓ": "fi", "ŕ": "fi", "Ȓ": "fl", "Ȕ": "fl", "ȳ": "ffl"}


def _elemen_teks(x, dx: float = 0, dy: float = 0, keluar: list | None = None) -> list:
    """(y, x, tinggi, ukuran huruf, teks) dari elemen teks, termasuk di dalam grup."""
    keluar = [] if keluar is None else keluar
    if isinstance(x, dict):
        if x.get("type") == "text" and x.get("visible", True) and str(x.get("text", "")).strip():
            keluar.append((x["y"] + dy, x["x"] + dx, x.get("height", 0), x.get("fontSize", 0), x["text"]))
        anak = x.get("children")
        if anak:
            grup = x.get("type") == "group"
            for a in anak:
                _elemen_teks(a, dx + (x.get("x", 0) if grup else 0), dy + (x.get("y", 0) if grup else 0), keluar)
    elif isinstance(x, list):
        for a in x:
            _elemen_teks(a, dx, dy, keluar)
    return keluar


def susun_halaman(halaman: dict, buang: re.Pattern | None = None) -> str:
    """Menyusun ulang teks satu halaman dari posisi tiap potong teks: atas ke bawah,
    kiri ke kanan, dengan baris kosong di antara blok yang berjarak jauh."""
    elemen = _elemen_teks(halaman.get("children", []))
    elemen.sort(key=lambda e: (round(e[0] / 4), e[1]))
    baris: list[str] = []
    y_lalu = bawah_lalu = None
    for y, x, tinggi, ukuran, teks in elemen:
        teks = html.unescape(re.sub(r"<[^>]+>", "", teks)).strip()
        for lama, baru in LIGATUR.items():
            teks = teks.replace(lama, baru)
        if not teks or (buang and buang.fullmatch(teks)):
            continue
        if y_lalu is not None and abs(y - y_lalu) < max(ukuran, 6) * 0.5:
            baris[-1] += " " + teks
        else:
            if bawah_lalu is not None and y - bawah_lalu > max(ukuran, 8) * 0.8:
                baris.append("")
            baris.append(teks)
        y_lalu, bawah_lalu = y, y + tinggi
    return "\n".join(baris)


def teks_tata_letak(berkas: Path, sumber: dict) -> list[tuple[str, int | None]]:
    """Teks dari ekspor tata letak JSON (halaman berisi elemen teks berposisi).

    sumber["halaman"] = [awal, akhir] dalam nomor halaman berkas; sumber["geser_halaman"]
    mengubahnya ke nomor halaman cetak; sumber["buang"] = pola baris kepala/kaki halaman.
    """
    data = json.loads(berkas.read_text(encoding="utf-8-sig"))
    halaman = data["pages"]
    awal, akhir = sumber.get("halaman") or [1, len(halaman)]
    geser = sumber.get("geser_halaman", 0)
    buang = re.compile(sumber["buang"]) if sumber.get("buang") else None
    hasil = []
    for nomor in range(max(awal, 1), min(akhir, len(halaman)) + 1):
        teks = susun_halaman(halaman[nomor - 1], buang)
        hasil.append((teks, nomor - geser if nomor > geser else None))
    return hasil


# ---------------------------------------------------------------- potong


def rapikan(teks: str) -> str:
    teks = re.sub(r"-\n(?=[a-z])", "", teks)  # kata terpotong di akhir baris PDF
    teks = re.sub(r"[ \t ]+", " ", teks)
    return teks


def potong(teks: str) -> list[str]:
    """Memotong teks jadi paragraf 30-140 kata, menggabungkan yang terlalu pendek."""
    hasil: list[str] = []
    kumpul = ""
    for blok in re.split(r"\n\s*\n", rapikan(teks)):
        blok = " ".join(blok.split())
        if not blok:
            continue
        kumpul = f"{kumpul} {blok}".strip() if kumpul else blok
        kata = kumpul.split()
        while len(kata) > MAKS_KATA:
            # Potong di akhir kalimat terdekat sebelum batas.
            potongan = " ".join(kata[:MAKS_KATA])
            titik = potongan.rfind(". ")
            if titik > len(potongan) // 2:
                potongan = potongan[: titik + 1]
            hasil.append(potongan)
            kata = kata[len(potongan.split()) :]
        kumpul = " ".join(kata)
        if len(kata) >= MIN_KATA:
            hasil.append(kumpul)
            kumpul = ""
    if len(kumpul.split()) >= MIN_KATA:
        hasil.append(kumpul)
    return hasil


def paragraf_dari(sumber: dict, potongan: list[tuple[str, int | None]]) -> list[dict]:
    hasil = []
    for teks, halaman in potongan:
        for p in potong(teks):
            if not KATA_RELEVAN.search(p):
                continue
            hasil.append(
                {
                    "sumber": sumber["id"],
                    "halaman": halaman,
                    "teks": p,
                    "bunyi": tandai_bunyi(p),
                    "pembaca": tandai_pembaca(p),
                }
            )
    return hasil


# ------------------------------------------------------------------ utama


def kumpulkan(daftar: list[dict], jeda: float) -> dict:
    sumber_jadi, semua = [], []
    for s in daftar:
        print(f"- {s['id']}: {s['judul']}")
        try:
            if s["jenis"] == "wikipedia":
                potongan, url = teks_wikipedia(s["judul_halaman"], s.get("bahasa", "id"), jeda)
                s = {**s, "url": url}
            elif s["jenis"] == "tata_letak":
                potongan = teks_tata_letak((AKAR / s["berkas"]).resolve(), s)
            else:
                if not boleh_diambil(s["url"]):
                    print("    dilewati: dilarang robots.txt")
                    continue
                data = unduh(s["url"], jeda)
                potongan = teks_pdf(data, s.get("halaman")) if s["jenis"] == "pdf" else teks_html(data)
        except Exception as galat:  # satu sumber gagal tidak menghentikan yang lain
            print(f"    dilewati: {type(galat).__name__}: {galat}")
            continue
        paragraf = paragraf_dari(s, potongan)
        print(f"    {len(paragraf)} paragraf relevan")
        if paragraf:
            semua.extend(paragraf)
            sumber_jadi.append(
                {k: s.get(k) for k in ("id", "judul", "url", "jenis", "lisensi", "penerbit", "bobot")}
            )
    for nomor, p in enumerate(semua, start=1):
        p["id"] = f"P{nomor}"
    return {"dibuat": time.strftime("%Y-%m-%d"), "sumber": sumber_jadi, "paragraf": semua}


def main() -> None:
    argumen = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumen.add_argument("--sumber", type=Path, default=FOLDER / "sumber.json")
    argumen.add_argument("--keluaran", type=Path, default=TUJUAN)
    argumen.add_argument("--jeda", type=float, default=1.5, help="detik antar permintaan")
    pilihan = argumen.parse_args()

    daftar = json.loads(pilihan.sumber.read_text(encoding="utf-8"))["sumber"]
    hasil = kumpulkan([s for s in daftar if s.get("aktif", True)], pilihan.jeda)
    pilihan.keluaran.parent.mkdir(parents=True, exist_ok=True)
    pilihan.keluaran.write_text(json.dumps(hasil, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n{len(hasil['paragraf'])} paragraf dari {len(hasil['sumber'])} sumber -> {pilihan.keluaran}")


if __name__ == "__main__":
    main()
