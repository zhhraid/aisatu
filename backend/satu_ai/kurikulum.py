"""Isi latihan: bunyi, tingkat, parameter BKT, dan bank kata.

Semua angka di sini titik awal yang ditebak, bukan hasil fit data.
Bank kata adalah usulan; cocokkan dengan buku guru sebelum dipakai.
"""

from dataclasses import dataclass

# "M" = bibir mengatup (m, b, p).
# Bentuk yang dinilai. "M" = bibir menutup (m, b, p), "F" = gigi dan bibir (f, v),
# "H" = hembusan napas (h, dari mikrofon). w dinilai sebagai "u", y sebagai "i".
# Huruf yang dibentuk lidah dinilai SEBAGIAN (posisi mulut dan suaranya, bukan lidah):
# "S" = desis (s, c, x, z, j), "T" = huruf lidah lain (t, d, n, l, r, k, g, q).
BUNYI: tuple[str, ...] = ("a", "i", "u", "o", "M", "e", "F", "H", "S", "T")

# Bunyi yang hanya dinilai sebagian: kamera tidak bisa melihat lidah.
DINILAI_SEBAGIAN: frozenset[str] = frozenset({"S", "T"})
TINGKAT: tuple[int, ...] = (1, 2, 3, 4)

NAMA_TINGKAT = {
    1: "Bunyi dengan bantuan",
    2: "Bunyi tanpa bantuan",
    3: "Suku kata",
    4: "Kata 2 suku",
}


@dataclass(frozen=True)
class ParamBKT:
    awal: float  # peluang sudah menguasai sebelum latihan pertama
    belajar: float  # peluang jadi menguasai setelah satu percobaan
    tebak: float  # peluang berhasil padahal belum menguasai
    salah: float  # peluang gagal padahal sudah menguasai


# Dipilih lewat simulasi supaya anak yang berhasil sekitar separuh percobaan jarang dicap
# "sudah bisa", dan anak yang berhasil 80% hampir selalu dicap begitu. Tebak dan salah
# dibuat sama di semua tingkat karena belum ada data untuk membedakannya.
_BELAJAR, _TEBAK, _SALAH = 0.05, 0.35, 0.10
PARAM: dict[int, ParamBKT] = {
    1: ParamBKT(awal=0.30, belajar=_BELAJAR, tebak=_TEBAK, salah=_SALAH),
    2: ParamBKT(awal=0.20, belajar=_BELAJAR, tebak=_TEBAK, salah=_SALAH),
    3: ParamBKT(awal=0.15, belajar=_BELAJAR, tebak=_TEBAK, salah=_SALAH),
    4: ParamBKT(awal=0.10, belajar=_BELAJAR, tebak=_TEBAK, salah=_SALAH),
}

AMBANG_PRASYARAT = 0.60
AMBANG_TUNTAS = 0.95
AMBANG_SUDAH_BISA = 0.85
AMBANG_HAMPIR_BISA = 0.50
PARUH_LUPA_HARI = 30.0  # asumsi: tanpa latihan, separuh kemajuan hilang dalam sebulan

_BENTUK_HURUF = {
    "a": "a", "i": "i", "u": "u", "e": "e", "o": "o",
    "m": "M", "b": "M", "p": "M",
    "f": "F", "v": "F",
    "w": "u", "y": "i",
    "h": "H",
    "s": "S", "c": "S", "x": "S", "z": "S", "j": "S",
    "t": "T", "d": "T", "n": "T", "l": "T", "r": "T", "k": "T", "g": "T", "q": "T",
}


def urutan_dari_teks(teks: str) -> tuple[str, ...]:
    """Urutan bentuk yang dinilai. Dua bentuk sama yang berurutan digabung
    (misalnya "ng" menjadi satu "T")."""
    hasil: list[str] = []
    for huruf in teks.lower():
        bentuk = _BENTUK_HURUF.get(huruf)
        if bentuk is None:
            continue
        if not hasil or hasil[-1] != bentuk:
            hasil.append(bentuk)
    return tuple(hasil)


@dataclass(frozen=True)
class Item:
    id: str
    tingkat: int
    teks: str
    urutan: tuple[str, ...]

    @property
    def bunyi(self) -> tuple[str, ...]:
        """Bunyi yang berbeda di item ini, urut kemunculan."""
        return tuple(dict.fromkeys(self.urutan))

    def ke_dict(self) -> dict:
        return {
            "id": self.id,
            "tingkat": self.tingkat,
            "teks": self.teks,
            "urutan": list(self.urutan),
            "bantuan_visual": self.tingkat == 1,
            # True kalau ada bunyi lidah yang hanya dinilai sebagian (mulut dan suara).
            "dinilai_sebagian": any(b in DINILAI_SEBAGIAN for b in self.urutan),
        }


SUKU_KATA = (
    "ma", "mi", "mu", "mo", "ba", "bi", "bu", "bo", "pa", "pi", "pu", "po",
    "me", "be", "pe", "fa", "fi", "fu", "va", "wa", "ya", "ha", "hi", "hu", "ho",
    "sa", "si", "su", "ca", "ja", "ta", "ti", "tu", "da", "ka", "ki", "ku", "ga", "la", "na", "ra",
)

BANK_KATA = (
    # Level 4 rancangan tim: kata 2 suku tanpa h.
    "mama", "mami", "oma", "ayam", "imam", "umum", "maaf", "mau", "ayo",
    # Level 5 rancangan tim: kata dengan h.
    "hiu", "hama", "hawa", "ayah", "wahyu",
    # Kata lain dari usulan awal (cocokkan dengan buku guru).
    "papa", "bola", "buku", "baju", "mata", "pipi", "bibi",
    "bumi", "pita", "palu", "mobil", "ibu", "api", "ubi", "topi",
    "sapu", "kaki", "kuda", "roti", "dadu", "susu", "gigi", "meja",
)

_TEKS_BUNYI = {
    "a": "a", "i": "i", "u": "u", "o": "o", "M": "m", "e": "e", "F": "f", "H": "h", "S": "s", "T": "t",
}


def _buat_item() -> tuple[Item, ...]:
    daftar: list[Item] = []
    for tingkat in (1, 2):
        for b in BUNYI:
            daftar.append(Item(f"t{tingkat}-{b}", tingkat, _TEKS_BUNYI[b], (b,)))
    for suku in SUKU_KATA:
        daftar.append(Item(f"t3-{suku}", 3, suku, urutan_dari_teks(suku)))
    for kata in BANK_KATA:
        daftar.append(Item(f"t4-{kata}", 4, kata, urutan_dari_teks(kata)))
    return tuple(daftar)


ITEM: tuple[Item, ...] = _buat_item()
ITEM_PER_ID: dict[str, Item] = {it.id: it for it in ITEM}


def label_penguasaan(p: float) -> str:
    if p >= AMBANG_SUDAH_BISA:
        return "sudah_bisa"
    if p >= AMBANG_HAMPIR_BISA:
        return "hampir_bisa"
    return "sedang_dilatih"


# Nama tahap untuk orang tua.
NAMA_TAHAP = {1: "bunyi tunggal dengan bantuan gambar", 2: "bunyi tunggal", 3: "suku kata", 4: "kata"}

TEKS_LABEL = {
    "sudah_bisa": "Sudah bisa",
    "hampir_bisa": "Hampir bisa",
    "sedang_dilatih": "Sedang dilatih",
    "belum_dilatih": "Belum dilatih",
}
WARNA_LABEL = {
    "sudah_bisa": "hijau",
    "hampir_bisa": "kuning",
    "sedang_dilatih": "merah",
    "belum_dilatih": "abu",
}

# GANTI dengan tips dari buku guru. Teks di bawah hanya pengisi sementara.
TIPS_PENDAMPING = (
    "Duduk berhadapan di tempat terang supaya anak bisa melihat bibir Anda dengan jelas.",
    "Latihan sebentar tapi rutin, sekitar lima menit, lebih baik daripada lama tapi jarang.",
    "Ucapkan kata pelan-pelan lebih dulu, lalu minta anak meniru sambil melihat cermin.",
    "Beri pujian setiap kali anak mencoba, bukan hanya saat berhasil.",
)
