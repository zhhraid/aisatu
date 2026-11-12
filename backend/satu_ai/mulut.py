"""Mulut: teks untuk guru dan orang tua.

Aturan yang dijaga di sini:
- LLM tidak memilih kata dan tidak menulis angka. Kata datang dari Otak.
- Nama anak tidak dikirim ke LLM; dipakai penanda ANAK lalu diganti server.
- Keluaran LLM diperiksa program. Kalau tidak lolos, dipakai templat.
"""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from . import llm
from .kurikulum import BANK_KATA, NAMA_TAHAP, NAMA_TINGKAT, SUKU_KATA, TEKS_LABEL

PemanggilLLM = Callable[[str, str], Awaitable[dict | None]]

_NAMA_BUNYI = {"a": "a", "i": "i", "u": "u", "o": "o", "M": "m/b/p"}
_KATA_LATIHAN = set(BANK_KATA) | set(SUKU_KATA)
_ANGKA = re.compile(r"\d")


def nama_bunyi(bunyi: str) -> str:
    return _NAMA_BUNYI.get(bunyi, bunyi)


def _gabung(daftar: list[str]) -> str:
    if not daftar:
        return "-"
    if len(daftar) == 1:
        return daftar[0]
    return ", ".join(daftar[:-1]) + " dan " + daftar[-1]


# ---------------------------------------------------------------------- pagar


def periksa_teks(teks: object, maks_kata: int, kata_boleh: set[str] | None = None) -> str | None:
    """Mengembalikan alasan penolakan, atau None kalau lolos.

    kata_boleh diisi hanya untuk alasan tugas: teks tidak boleh menyebut kata latihan
    selain yang ada di situ. Untuk laporan dibiarkan None, karena kata seperti "ibu"
    dan "mata" wajar muncul di kalimat biasa.
    """
    if not isinstance(teks, str) or not teks.strip():
        return "kosong"
    if _ANGKA.search(teks):
        return "memuat angka"
    kata = re.findall(r"[a-zA-Z]+", teks.lower())
    if len(kata) > maks_kata:
        return "terlalu panjang"
    if kata_boleh is not None:
        asing = (set(kata) & _KATA_LATIHAN) - kata_boleh
        if asing:
            return f"menyebut kata latihan lain: {sorted(asing)}"
    return None


def _isi_nama(teks: str, nama: str) -> str:
    return teks.replace("ANAK", nama)


# ------------------------------------------------- A. alasan usulan tugas

SISTEM_ALASAN = (
    "Kamu membantu guru bina wicara di SLB. Untuk tiap kata yang diberikan, tulis satu kalimat "
    "alasan mengapa kata itu cocok dilatih hari ini, berdasarkan data yang diberikan saja. "
    "Pakai bahasa Indonesia sederhana. Jangan menyebut angka. Jangan menambah kata latihan lain. "
    "Jangan memberi diagnosis atau janji hasil. Sebut anak sebagai ANAK. "
    'Jawab hanya JSON: {"tugas": [{"kata": "...", "alasan": "..."}]} dengan urutan kata yang sama. '
    "Alasan paling banyak 20 kata."
)


def _templat_alasan(t: dict) -> str:
    bunyi = nama_bunyi(t["bunyi_fokus"])
    label = TEKS_LABEL[t["label"]].lower()
    hari = t.get("hari_sejak_latihan")
    if t["label"] == "belum_dilatih" or hari is None:
        return f"Bunyi {bunyi} belum pernah dilatih di tingkat ini."
    kapan = "hari ini" if hari == 0 else "kemarin" if hari == 1 else f"{hari} hari lalu"
    return f"Bunyi {bunyi} berstatus {label} dan terakhir dilatih {kapan}."


async def alasan_tugas(
    usulan: list[dict], nama: str, pemanggil: PemanggilLLM | None = None
) -> dict:
    """usulan = keluaran otak.usul_tugas(). Menambahkan alasan pada tiap butir."""
    pemanggil = pemanggil or llm.panggil_json
    kata = [u["item"]["teks"] for u in usulan]
    cadangan = [_isi_nama(_templat_alasan(u), nama) for u in usulan]

    masukan = [
        {
            "kata": u["item"]["teks"],
            "jenis": NAMA_TINGKAT[u["item"]["tingkat"]],
            "bunyi_lemah": nama_bunyi(u["bunyi_fokus"]),
            "status": TEKS_LABEL[u["label"]],
            "terakhir_dilatih": (
                "belum pernah"
                if u.get("hari_sejak_latihan") is None
                else "hari ini" if u["hari_sejak_latihan"] == 0
                else "beberapa hari lalu"
            ),
        }
        for u in usulan
    ]
    jawab = await pemanggil(SISTEM_ALASAN, json.dumps(masukan, ensure_ascii=False))

    alasan, sumber = cadangan, "templat"
    if jawab:
        butir = jawab.get("tugas")
        lolos = (
            isinstance(butir, list)
            and len(butir) == len(usulan)
            and all(isinstance(b, dict) for b in butir)
            and [b.get("kata") for b in butir] == kata
            and all(periksa_teks(b.get("alasan"), 20, {k}) is None for b, k in zip(butir, kata))
        )
        if lolos:
            alasan = [_isi_nama(b["alasan"].strip(), nama) for b in butir]
            sumber = "llm"

    return {
        "tugas": [{**u, "alasan": a} for u, a in zip(usulan, alasan)],
        "sumber": sumber,
    }


# ------------------------------------------------------ B. ringkasan kelas

SISTEM_RINGKASAN = (
    "Tulis ringkasan kelas dalam dua sampai tiga kalimat untuk guru bina wicara: siapa yang perlu "
    "perhatian dan di bunyi apa, lalu satu hal yang membaik. Pakai hanya data yang diberikan. "
    "Sebut anak persis dengan penanda yang diberikan (misalnya ANAK_1). Jangan menyebut angka "
    "selain di penanda itu. Jangan memberi saran medis. "
    'Jawab hanya JSON: {"ringkasan": "..."} paling banyak 60 kata.'
)


def _templat_ringkasan(kelas: list[dict]) -> str:
    perlu = [
        f"{a['penanda']} (bunyi {_gabung([nama_bunyi(b) for b in a['macet']])})"
        for a in kelas
        if a["macet"]
    ]
    naik = [
        f"{a['penanda']} (bunyi {_gabung([nama_bunyi(b) for b in a['naik']])})"
        for a in kelas
        if a["naik"]
    ]
    bagian = []
    bagian.append(
        f"Yang perlu perhatian: {_gabung(perlu)}." if perlu else "Belum ada anak yang macet di satu bunyi."
    )
    bagian.append(f"Yang membaik minggu ini: {_gabung(naik)}." if naik else "Belum ada bunyi yang baru tercapai minggu ini.")
    return " ".join(bagian)


async def ringkasan_kelas(anak: list[dict], pemanggil: PemanggilLLM | None = None) -> dict:
    """anak = [{"nama": str, "macet": [bunyi], "naik": [bunyi]}]."""
    pemanggil = pemanggil or llm.panggil_json
    kelas = [
        {"penanda": f"ANAK_{i}", "nama": a["nama"], "macet": a["macet"], "naik": a["naik"]}
        for i, a in enumerate(anak, start=1)
    ]

    def isi_nama(teks: str) -> str:
        # Penanda bernomor besar dulu, supaya ANAK_1 tidak memotong ANAK_10.
        for a in reversed(kelas):
            teks = teks.replace(a["penanda"], a["nama"])
        return teks

    teks, sumber = _templat_ringkasan(kelas), "templat"
    if kelas:
        masukan = [
            {
                "anak": a["penanda"],
                "bunyi_macet": [nama_bunyi(b) for b in a["macet"]],
                "bunyi_membaik": [nama_bunyi(b) for b in a["naik"]],
            }
            for a in kelas
        ]
        jawab = await pemanggil(SISTEM_RINGKASAN, json.dumps(masukan, ensure_ascii=False))
        calon = jawab.get("ringkasan") if jawab else None
        if isinstance(calon, str):
            tanpa_penanda = re.sub(r"ANAK_\d+", "ANAK", calon)
            penanda_asing = set(re.findall(r"ANAK_\d+", calon)) - {a["penanda"] for a in kelas}
            if periksa_teks(tanpa_penanda, 60) is None and not penanda_asing:
                teks, sumber = calon.strip(), "llm"
    return {"ringkasan": isi_nama(teks), "sumber": sumber}


# --------------------------------------------- C. laporan mingguan orang tua

SISTEM_LAPORAN = (
    "Tulis laporan singkat untuk orang tua anak tunarungu. Nada hangat dan apa adanya, tanpa "
    "istilah teknis. Tiga bagian: yang sudah bisa, yang sedang dilatih, cara membantu di rumah. "
    "Untuk cara membantu, pakai tips yang diberikan dengan kata-katamu sendiri; jangan menambah "
    "tips lain. Jangan menyebut angka, jangan membandingkan dengan anak lain, jangan menjanjikan "
    "hasil. Sebut anak sebagai ANAK. "
    'Jawab hanya JSON: {"sudah_bisa": "...", "sedang_dilatih": "...", "cara_membantu": "..."} '
    "tiap bagian paling banyak 30 kata."
)

_BAGIAN_LAPORAN = ("sudah_bisa", "sedang_dilatih", "cara_membantu")


def _per_tahap(daftar: list[dict]) -> str:
    """[{"bunyi", "tingkat"}] -> "bunyi a dan i di tahap suku kata; bunyi o di tahap kata"."""
    kelompok: dict[int, list[str]] = {}
    for d in daftar:
        kelompok.setdefault(d["tingkat"], []).append(nama_bunyi(d["bunyi"]))
    return "; ".join(
        f"bunyi {_gabung(bunyi)} di tahap {NAMA_TAHAP[tingkat]}"
        for tingkat, bunyi in sorted(kelompok.items(), reverse=True)
    )


def _templat_laporan(data: dict) -> dict:
    return {
        "sudah_bisa": (
            f"ANAK sudah bisa {_per_tahap(data['sudah_bisa'])}."
            if data["sudah_bisa"]
            else "ANAK masih di tahap awal latihan."
        ),
        "sedang_dilatih": (
            f"Saat ini ANAK berlatih {_per_tahap(data['sedang_dilatih'])}."
            if data["sedang_dilatih"]
            else "Belum ada bunyi baru yang sedang dilatih."
        ),
        "cara_membantu": data["tips"],
    }


async def laporan_mingguan(data: dict, nama: str, pemanggil: PemanggilLLM | None = None) -> dict:
    """data = {"sudah_bisa": [{"bunyi", "tingkat"}], "sedang_dilatih": [{"bunyi", "tingkat"}],
    "hari_latihan": int, "tips": str}. Satu bunyi boleh muncul di keduanya: sudah bisa di
    tahap bawah dan sedang berlatih di tahap atasnya."""
    pemanggil = pemanggil or llm.panggil_json
    hari = data.get("hari_latihan", 0)

    def untuk_llm(daftar: list[dict]) -> list[dict]:
        return [{"bunyi": nama_bunyi(d["bunyi"]), "tahap": NAMA_TAHAP[d["tingkat"]]} for d in daftar]

    masukan = {
        "sudah_bisa": untuk_llm(data["sudah_bisa"]),
        "sedang_dilatih": untuk_llm(data["sedang_dilatih"]),
        "rutinitas_minggu_ini": "hampir setiap hari" if hari >= 5 else "beberapa hari" if hari >= 2 else "jarang",
        "tips": data["tips"],
    }
    jawab = await pemanggil(SISTEM_LAPORAN, json.dumps(masukan, ensure_ascii=False))

    bagian, sumber = _templat_laporan(data), "templat"
    if jawab and all(periksa_teks(jawab.get(k), 30) is None for k in _BAGIAN_LAPORAN):
        bagian = {k: jawab[k].strip() for k in _BAGIAN_LAPORAN}
        sumber = "llm"
    return {**{k: _isi_nama(v, nama) for k, v in bagian.items()}, "hari_latihan": hari, "sumber": sumber}
