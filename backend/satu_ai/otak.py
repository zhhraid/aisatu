"""Otak: penguasaan per bunyi x tingkat, pemilih latihan, dan usulan tugas.

Semua fungsi di sini murni terhadap StatusAnak yang diberikan; penyimpanan
diurus pemanggil. StatusAnak bisa disimpan sebagai satu kolom JSON per anak.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import bkt
from .kurikulum import (
    AMBANG_PRASYARAT,
    AMBANG_SUDAH_BISA,
    AMBANG_TUNTAS,
    BUNYI,
    ITEM,
    PARAM,
    PARUH_LUPA_HARI,
    TINGKAT,
    Item,
    label_penguasaan,
    LEVEL,
)

TARGET_BERHASIL = 0.78  # tengah rentang 70-85%
BATAS_BAWAH = 0.70
BATAS_ATAS = 0.85
UKURAN_JENDELA = 10
MIN_JENDELA = 5  # jangan menilai tingkat berhasil dari kurang dari 5 percobaan
GAGAL_UNTUK_ISTIRAHAT = 3
MAKS_ULANG = 3
PELUANG_JELAJAH = 0.10
JEDA_SESI_BARU = timedelta(minutes=30)
MIN_PERCOBAAN_MACET = 6


# Hari latihan dan streak dihitung menurut tanggal WIB, bukan UTC, supaya latihan
# pukul 06.00 pagi tidak tercatat sebagai hari sebelumnya.
WIB = timezone(timedelta(hours=7))


def tanggal_lokal(t: datetime) -> str:
    return t.astimezone(WIB).date().isoformat()


def sekarang_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class KC:
    """Penguasaan satu bunyi di satu tingkat."""

    p: float
    n: int = 0
    terakhir: datetime | None = None
    tercapai_pada: datetime | None = None  # pertama kali mencapai "sudah bisa"
    tuntas: bool = False  # pernah tuntas dan belum turun lagi di bawah "sudah bisa"


@dataclass
class StatusAnak:
    kc: dict[tuple[str, int], KC] = field(default_factory=dict)
    jendela: list[bool] = field(default_factory=list)  # hasil terakhir di sesi ini
    gagal_beruntun: int = 0
    item_terakhir: str | None = None
    ulang_beruntun: int = 0
    turun: dict | None = None  # {"bunyi", "tingkat"} setelah 3 gagal beruntun
    percobaan_terakhir: datetime | None = None
    hari_latihan: list[str] = field(default_factory=list)  # tanggal ISO, unik
    sintetis: bool = False  # True untuk data demo buatan
    # Riwayat per tanggal WIB: {"percobaan", "berhasil", "kc": {"bunyi:tingkat": p terakhir hari itu}}
    riwayat: dict[str, dict] = field(default_factory=dict)
    tadi_penguatan: bool = False  # latihan terakhir adalah item yang sudah dikuasai
    model_bibir: dict | None = None  # model bibir personal dari Mata (nearest centroid)
    # Sesi ini, untuk deteksi lelah: kapan mulai, hasil, dan lama tiap percobaan.
    sesi_mulai: datetime | None = None
    hasil_sesi: list[bool] = field(default_factory=list)
    durasi_sesi: list[int] = field(default_factory=list)

    def ambil(self, bunyi: str, tingkat: int) -> KC:
        kunci = (bunyi, tingkat)
        if kunci not in self.kc:
            self.kc[kunci] = KC(p=PARAM[tingkat].awal)
        return self.kc[kunci]

    def ke_dict(self) -> dict:
        def iso(t: datetime | None) -> str | None:
            return t.isoformat() if t else None

        return {
            "kc": {
                f"{b}:{t}": {
                    "p": k.p,
                    "n": k.n,
                    "terakhir": iso(k.terakhir),
                    "tercapai_pada": iso(k.tercapai_pada),
                    "tuntas": k.tuntas,
                }
                for (b, t), k in self.kc.items()
            },
            "jendela": list(self.jendela),
            "gagal_beruntun": self.gagal_beruntun,
            "item_terakhir": self.item_terakhir,
            "ulang_beruntun": self.ulang_beruntun,
            "turun": self.turun,
            "percobaan_terakhir": iso(self.percobaan_terakhir),
            "hari_latihan": list(self.hari_latihan),
            "sintetis": self.sintetis,
            "riwayat": self.riwayat,
            "tadi_penguatan": self.tadi_penguatan,
            "model_bibir": self.model_bibir,
            "sesi_mulai": iso(self.sesi_mulai),
            "hasil_sesi": list(self.hasil_sesi),
            "durasi_sesi": list(self.durasi_sesi),
        }

    @classmethod
    def dari_dict(cls, d: dict) -> "StatusAnak":
        def waktu(s: str | None) -> datetime | None:
            return datetime.fromisoformat(s) if s else None

        status = cls()
        for kunci, k in d.get("kc", {}).items():
            bunyi, tingkat = kunci.split(":")
            status.kc[(bunyi, int(tingkat))] = KC(
                p=k["p"],
                n=k.get("n", 0),
                terakhir=waktu(k.get("terakhir")),
                tercapai_pada=waktu(k.get("tercapai_pada")),
                tuntas=k.get("tuntas", False),
            )
        status.jendela = list(d.get("jendela", []))
        status.gagal_beruntun = d.get("gagal_beruntun", 0)
        status.item_terakhir = d.get("item_terakhir")
        status.ulang_beruntun = d.get("ulang_beruntun", 0)
        status.turun = d.get("turun")
        status.percobaan_terakhir = waktu(d.get("percobaan_terakhir"))
        status.hari_latihan = list(d.get("hari_latihan", []))
        status.sintetis = d.get("sintetis", False)
        status.riwayat = {t: {**r, "kc": dict(r.get("kc", {}))} for t, r in d.get("riwayat", {}).items()}
        status.tadi_penguatan = d.get("tadi_penguatan", False)
        status.model_bibir = d.get("model_bibir")
        status.sesi_mulai = waktu(d.get("sesi_mulai"))
        status.hasil_sesi = list(d.get("hasil_sesi", []))
        status.durasi_sesi = list(d.get("durasi_sesi", []))
        return status


# ---------------------------------------------------------------- penguasaan


def p_kini(status: StatusAnak, bunyi: str, tingkat: int, sekarang: datetime) -> float:
    """Penguasaan saat ini, sudah memperhitungkan lupa."""
    k = status.kc.get((bunyi, tingkat))
    awal = PARAM[tingkat].awal
    if k is None:
        return awal
    if k.terakhir is None:
        return k.p
    hari = (sekarang - k.terakhir).total_seconds() / 86400
    return bkt.luruh(k.p, awal, hari, PARUH_LUPA_HARI)


def p_item(status: StatusAnak, item: Item, sekarang: datetime) -> float:
    """Penguasaan sebuah item = bunyi terlemahnya di tingkat itu."""
    return min(p_kini(status, b, item.tingkat, sekarang) for b in item.bunyi)


def prasyarat_terpenuhi(status: StatusAnak, item: Item, sekarang: datetime) -> bool:
    """Tiap bunyi cukup dikuasai di tingkat bawahnya, atau sudah pernah dilatih dan cukup
    dikuasai di tingkat ini sendiri (supaya kemunduran di tingkat bawah tidak mengunci
    tingkat yang sudah berjalan)."""
    if item.tingkat == 1:
        return True

    def cukup(bunyi: str) -> bool:
        if p_kini(status, bunyi, item.tingkat - 1, sekarang) >= AMBANG_PRASYARAT:
            return True
        k = status.kc.get((bunyi, item.tingkat))
        return (
            k is not None
            and k.n > 0
            and p_kini(status, bunyi, item.tingkat, sekarang) >= AMBANG_PRASYARAT
        )

    return all(cukup(b) for b in item.bunyi)


def perkiraan_item(status: StatusAnak, item: Item, sekarang: datetime) -> float:
    return bkt.perkiraan_berhasil(p_item(status, item, sekarang), PARAM[item.tingkat])


# ------------------------------------------------------------------- mencatat


def mulai_sesi(status: StatusAnak) -> None:
    status.jendela = []
    status.gagal_beruntun = 0
    status.ulang_beruntun = 0
    status.turun = None
    status.sesi_mulai = None
    status.hasil_sesi = []
    status.durasi_sesi = []


def catat_percobaan(
    status: StatusAnak,
    item: Item,
    berhasil: bool,
    langkah_tercapai: int,
    sekarang: datetime,
    durasi_ms: int | None = None,
) -> list[dict]:
    """Memperbarui penguasaan dari satu percobaan. Mengembalikan daftar perubahan.

    langkah_tercapai = jumlah langkah urutan yang sudah dilewati. Kalau gagal,
    bunyi di posisi itu adalah tempat anak macet.
    """
    if status.percobaan_terakhir and sekarang - status.percobaan_terakhir > JEDA_SESI_BARU:
        mulai_sesi(status)
    status.sesi_mulai = status.sesi_mulai or sekarang
    status.hasil_sesi = (status.hasil_sesi + [berhasil])[-200:]
    if durasi_ms is not None:
        status.durasi_sesi = (status.durasi_sesi + [durasi_ms])[-200:]

    macet: str | None = None
    if berhasil:
        hasil = {b: True for b in item.bunyi}
    else:
        posisi = max(0, min(langkah_tercapai, len(item.urutan) - 1))
        macet = item.urutan[posisi]
        hasil = {b: True for b in item.urutan[:posisi] if b != macet}
        hasil[macet] = False

    bkt_sebelum = {b: p_kini(status, b, item.tingkat, sekarang) for b in item.bunyi}
    perubahan = []
    param = PARAM[item.tingkat]
    for bunyi, ok in hasil.items():
        sebelum = p_kini(status, bunyi, item.tingkat, sekarang)
        sesudah = bkt.perbarui(sebelum, ok, param)
        k = status.ambil(bunyi, item.tingkat)
        k.p, k.n, k.terakhir = sesudah, k.n + 1, sekarang
        if sesudah >= AMBANG_SUDAH_BISA and k.tercapai_pada is None:
            k.tercapai_pada = sekarang
        if sesudah >= AMBANG_TUNTAS:
            k.tuntas = True
        elif sesudah < AMBANG_SUDAH_BISA:
            k.tuntas = False
        perubahan.append(
            {
                "bunyi": bunyi,
                "tingkat": item.tingkat,
                "berhasil": ok,
                "sebelum": round(sebelum, 4),
                "sesudah": round(sesudah, 4),
                "label": label_penguasaan(sesudah),
            }
        )

    status.jendela = (status.jendela + [berhasil])[-UKURAN_JENDELA:]
    status.ulang_beruntun = status.ulang_beruntun + 1 if status.item_terakhir == item.id else 1
    status.item_terakhir = item.id
    # Latihan yang sebelumnya sudah dikuasai dihitung sebagai penguatan.
    status.tadi_penguatan = all(p >= AMBANG_SUDAH_BISA for p in bkt_sebelum.values())
    status.percobaan_terakhir = sekarang

    status.turun = None
    status.gagal_beruntun = 0 if berhasil else status.gagal_beruntun + 1
    if status.gagal_beruntun >= GAGAL_UNTUK_ISTIRAHAT:
        status.turun = {"bunyi": macet, "tingkat": item.tingkat}
        status.gagal_beruntun = 0

    tanggal = tanggal_lokal(sekarang)
    if tanggal not in status.hari_latihan:
        status.hari_latihan = (status.hari_latihan + [tanggal])[-60:]
    catat_riwayat(status, tanggal, berhasil, {(c["bunyi"], c["tingkat"]): c["sesudah"] for c in perubahan})
    return perubahan


RIWAYAT_HARI = 60


def catat_riwayat(status: StatusAnak, tanggal: str, berhasil: bool, kc: dict[tuple[str, int], float]) -> None:
    hari = status.riwayat.setdefault(tanggal, {"percobaan": 0, "berhasil": 0, "kc": {}})
    hari["percobaan"] += 1
    hari["berhasil"] += int(berhasil)
    for (bunyi, tingkat), p in kc.items():
        hari["kc"][f"{bunyi}:{tingkat}"] = round(p, 4)
    for lama in sorted(status.riwayat)[:-RIWAYAT_HARI]:
        del status.riwayat[lama]


def riwayat(status: StatusAnak) -> dict:
    """Perkembangan dari waktu ke waktu, untuk grafik di aplikasi guru.

    kemajuan bunyi = (tingkat - 1 + penguasaan) / 4, jadi 0 sampai 1 melintasi keempat
    tingkat: naik tingkat dan naik penguasaan sama-sama terlihat sebagai garis naik.
    """
    harian, per_bunyi = [], {b: [] for b in BUNYI}
    for tanggal in sorted(status.riwayat):
        hari = status.riwayat[tanggal]
        harian.append(
            {
                "tanggal": tanggal,
                "percobaan": hari["percobaan"],
                "berhasil": hari["berhasil"],
                "tingkat_berhasil": round(hari["berhasil"] / hari["percobaan"], 3) if hari["percobaan"] else None,
            }
        )
        terbaik: dict[str, tuple[int, float]] = {}
        for kunci, p in hari["kc"].items():
            bunyi, tingkat = kunci.split(":")
            if int(tingkat) >= terbaik.get(bunyi, (0, 0.0))[0]:
                terbaik[bunyi] = (int(tingkat), p)
        for bunyi, (tingkat, p) in terbaik.items():
            per_bunyi.setdefault(bunyi, []).append(
                {"tanggal": tanggal, "tingkat": tingkat, "p": p, "kemajuan": round((tingkat - 1 + p) / 4, 3)}
            )
    return {"harian": harian, "per_bunyi": {b: v for b, v in per_bunyi.items() if v}}


# ---------------------------------------------------------------- level


def _kemajuan(status: StatusAnak, bunyi: str, tingkat: int, sekarang: datetime) -> float:
    """0 sampai 1 menuju "sudah bisa"; 0 kalau belum pernah dilatih."""
    k = status.kc.get((bunyi, tingkat))
    if not k or k.n == 0:
        return 0.0
    return min(1.0, p_kini(status, bunyi, tingkat, sekarang) / AMBANG_SUDAH_BISA)


# 40%: dipilih lewat simulasi; 60% menahan anak terlalu lama di level awal.
AMBANG_BUKA_LEVEL = 0.4


def status_level(status: StatusAnak, sekarang: datetime) -> dict:
    """Peta petualangan: kemajuan, bintang, dan status tiap level."""
    hasil, terbuka_sebelumnya = [], True
    for lv in LEVEL:
        nilai = [_kemajuan(status, b, t, sekarang) for b in lv.bunyi for t in lv.tingkat]
        kemajuan = sum(nilai) / len(nilai)
        pernah = any((k := status.kc.get((b, t))) and k.n > 0 for b in lv.bunyi for t in lv.tingkat)
        terbuka = lv.nomor == 1 or terbuka_sebelumnya or pernah
        tuntas = kemajuan >= 0.999
        hasil.append(
            {
                "level": lv.nomor,
                "nama": lv.nama,
                "kemajuan": round(kemajuan, 3),
                "bintang": 3 if tuntas else 2 if kemajuan >= 0.66 else 1 if kemajuan >= 0.33 else 0,
                "status": "tuntas" if tuntas else "terbuka" if terbuka else "terkunci",
            }
        )
        terbuka_sebelumnya = terbuka and kemajuan >= AMBANG_BUKA_LEVEL
    sekarang_lv = next((h["level"] for h in hasil if h["status"] == "terbuka"), LEVEL[-1].nomor)
    return {"level_sekarang": sekarang_lv, "level": hasil}


def level_terbuka_tertinggi(status: StatusAnak, sekarang: datetime) -> int:
    return max(h["level"] for h in status_level(status, sekarang)["level"] if h["status"] != "terkunci")


def tingkat_berhasil(status: StatusAnak) -> float | None:
    """Tingkat berhasil di sesi ini, atau None kalau datanya belum cukup."""
    if len(status.jendela) < MIN_JENDELA:
        return None
    return sum(status.jendela) / len(status.jendela)


# -------------------------------------------------------------------- memilih


@dataclass
class Pilihan:
    item: Item
    perkiraan: float
    # zona | penguatan | lebih_mudah | lebih_sulit | turun_tingkat | ganti_bunyi | jelajah | ulang_tuntas
    alasan: str
    istirahat: bool = False

    def ke_dict(self) -> dict:
        return {
            "item": self.item.ke_dict(),
            "perkiraan_berhasil": round(self.perkiraan, 3),
            "alasan": self.alasan,
            "istirahat": self.istirahat,
        }


def _sudah_lewat(status: StatusAnak, item: Item, sekarang: datetime) -> bool:
    """Semua bunyi item ini sudah dilatih dan cukup dikuasai di tingkat atasnya,
    jadi tidak perlu kembali ke tingkat ini."""
    atas = item.tingkat + 1
    if atas not in PARAM:
        return False
    return all(
        (k := status.kc.get((b, atas))) is not None
        and k.n > 0
        and p_kini(status, b, atas, sekarang) >= AMBANG_PRASYARAT
        for b in item.bunyi
    )


def _masih_tuntas(status: StatusAnak, item: Item, sekarang: datetime) -> bool:
    """Item yang sudah "sudah bisa" tidak dilatih lagi sampai turun karena lupa.

    Dipilih lewat simulasi (skrip/simulasi_otak.py): menunggu sampai 95% membuat anak
    terus mengulang yang sudah hampir dikuasai dan lebih sedikit belajar hal baru.
    """
    return p_item(status, item, sekarang) >= AMBANG_SUDAH_BISA


def _terbuka(status: StatusAnak, sekarang: datetime) -> list[Item]:
    """Item yang prasyaratnya terpenuhi dan levelnya sudah terbuka di peta."""
    batas = level_terbuka_tertinggi(status, sekarang)
    return [it for it in ITEM if it.level <= batas and prasyarat_terpenuhi(status, it, sekarang)]


def _kandidat(status: StatusAnak, sekarang: datetime) -> list[Item]:
    return [
        it
        for it in _terbuka(status, sekarang)
        if not _masih_tuntas(status, it, sekarang) and not _sudah_lewat(status, it, sekarang)
    ]


def _terdekat(
    status: StatusAnak,
    daftar: list[Item],
    target: float,
    sekarang: datetime,
    rng: random.Random | None,
) -> Item:
    """Item yang perkiraannya paling dekat ke target. rng=None: seri dipecah urutan kurikulum."""
    jarak = [(abs(perkiraan_item(status, it, sekarang) - target), it) for it in daftar]
    terbaik = min(j for j, _ in jarak)
    seri = [it for j, it in jarak if j - terbaik < 1e-6]
    return rng.choice(seri) if rng and len(seri) > 1 else seri[0]


def _pilih_setelah_gagal(
    status: StatusAnak, sekarang: datetime, rng: random.Random | None
) -> Pilihan | None:
    bunyi, tingkat = status.turun["bunyi"], status.turun["tingkat"]
    if tingkat > 1:
        bawah = [it for it in ITEM if it.tingkat == tingkat - 1 and bunyi in it.bunyi]
        # Yang paling mudah di tingkat bawah, supaya anak berhasil lagi.
        item = _terdekat(status, bawah, 1.0, sekarang, rng)
        return Pilihan(item, perkiraan_item(status, item, sekarang), "turun_tingkat", True)
    lain = [it for it in _kandidat(status, sekarang) if bunyi not in it.bunyi]
    if not lain:
        return None
    item = _terdekat(status, lain, 1.0, sekarang, rng)
    return Pilihan(item, perkiraan_item(status, item, sekarang), "ganti_bunyi", True)


def pilih_berikutnya(
    status: StatusAnak,
    sekarang: datetime,
    rng: random.Random | None = None,
) -> Pilihan:
    """Memilih latihan berikutnya. rng=None berarti tanpa acak (mode demo)."""
    if status.turun:
        pilihan = _pilih_setelah_gagal(status, sekarang, rng)
        if pilihan:
            return pilihan

    kandidat = _kandidat(status, sekarang)
    if not kandidat:
        # Tidak ada yang perlu dilatih: ulang yang paling lemah di tingkat tertinggi yang terbuka.
        terbuka = _terbuka(status, sekarang)
        puncak = max(it.tingkat for it in terbuka)
        item = min(
            (it for it in terbuka if it.tingkat == puncak),
            key=lambda it: p_item(status, it, sekarang),
        )
        return Pilihan(item, perkiraan_item(status, item, sekarang), "ulang_tuntas", bool(status.turun))

    alasan = "zona"
    tingkat_ada = sorted({it.tingkat for it in kandidat})
    laju = tingkat_berhasil(status)
    # Penguatan diselingi: tidak pernah dua latihan mudah berturut-turut, supaya anak
    # yang sering gagal tetap mendapat bahan baru (lihat skrip/simulasi_otak.py).
    if laju is not None and laju < BATAS_BAWAH and not status.tadi_penguatan:
        # Terlalu sering gagal: beri latihan yang kemungkinan besar berhasil, termasuk
        # yang sudah tuntas, supaya tingkat berhasil kembali ke rentang target.
        mudah = [it for it in _terbuka(status, sekarang) if perkiraan_item(status, it, sekarang) >= BATAS_BAWAH]
        if mudah:
            kandidat, alasan = mudah, "penguatan"
        elif len(tingkat_ada) > 1:
            kandidat = [it for it in kandidat if it.tingkat != tingkat_ada[-1]]
            alasan = "lebih_mudah"
    elif laju is not None and laju > BATAS_ATAS and len(tingkat_ada) > 1:
        kandidat = [it for it in kandidat if it.tingkat == tingkat_ada[-1]]
        alasan = "lebih_sulit"

    if status.ulang_beruntun >= MAKS_ULANG and len(kandidat) > 1:
        kandidat = [it for it in kandidat if it.id != status.item_terakhir]

    item = _terdekat(status, kandidat, TARGET_BERHASIL, sekarang, rng)
    if rng and len(kandidat) > 1 and rng.random() < PELUANG_JELAJAH:
        item = rng.choice([it for it in kandidat if it.id != item.id])
        alasan = "jelajah"
    return Pilihan(item, perkiraan_item(status, item, sekarang), alasan, bool(status.turun))


# ---------------------------------------------------------- peta dan insight


def tingkat_tercapai(status: StatusAnak, bunyi: str | None = None) -> int:
    """Tingkat tertinggi yang pernah dilatih (0 kalau belum pernah)."""
    return max(
        (t for (b, t), k in status.kc.items() if k.n > 0 and (bunyi is None or b == bunyi)),
        default=0,
    )


def peta(status: StatusAnak, sekarang: datetime) -> list[dict]:
    """Satu baris per bunyi: ringkasan di tingkat tertinggi yang pernah dilatih, plus rinciannya."""
    hasil = []
    for bunyi in BUNYI:
        rinci = []
        for tingkat in TINGKAT:
            k = status.kc.get((bunyi, tingkat))
            p = p_kini(status, bunyi, tingkat, sekarang)
            rinci.append(
                {
                    "tingkat": tingkat,
                    "p": round(p, 3),
                    "percobaan": k.n if k else 0,
                    "label": label_penguasaan(p) if k and k.n else "belum_dilatih",
                }
            )
        tingkat_atas = tingkat_tercapai(status, bunyi)
        ringkas = rinci[tingkat_atas - 1] if tingkat_atas else {"p": None, "label": "belum_dilatih"}
        hasil.append(
            {
                "bunyi": bunyi,
                "tingkat": tingkat_atas,  # tingkat tertinggi yang pernah dilatih
                "p": ringkas["p"],
                "label": ringkas["label"],  # status di tingkat itu
                "tingkat_tuntas": max(
                    (r["tingkat"] for r in rinci if r["label"] == "sudah_bisa"), default=0
                ),
                "rinci": rinci,
            }
        )
    return hasil


def insight(status: StatusAnak, sekarang: datetime) -> dict:
    """Aturan sederhana untuk guru: bunyi yang macet dan bunyi yang baru naik."""
    macet = []
    naik: dict[str, int] = {}
    for bunyi in BUNYI:
        for tingkat in TINGKAT:
            k = status.kc.get((bunyi, tingkat))
            if k is None:
                continue
            p = p_kini(status, bunyi, tingkat, sekarang)
            if k.n >= MIN_PERCOBAAN_MACET and p < 0.5:
                macet.append({"bunyi": bunyi, "tingkat": tingkat, "percobaan": k.n})
            if (
                k.tercapai_pada
                and sekarang - k.tercapai_pada <= timedelta(days=7)
                and p >= AMBANG_SUDAH_BISA
            ):
                naik[bunyi] = tingkat  # tingkat tertinggi yang baru tercapai
    bunyi_macet = {m["bunyi"] for m in macet}
    return {
        "macet": macet,
        "naik": [{"bunyi": b, "tingkat": t} for b, t in naik.items() if b not in bunyi_macet],
    }


def hari_latihan_minggu_ini(status: StatusAnak, sekarang: datetime) -> int:
    batas = tanggal_lokal(sekarang - timedelta(days=6))
    return sum(1 for tanggal in status.hari_latihan if tanggal >= batas)


def streak(status: StatusAnak, sekarang: datetime) -> int:
    """Jumlah hari berturut-turut berlatih. Tetap terhitung kalau hari ini belum
    berlatih tapi kemarin sudah; putus kalau kemarin juga tidak berlatih."""
    hari = set(status.hari_latihan)
    tanggal = sekarang.astimezone(WIB).date()
    if tanggal.isoformat() not in hari:
        tanggal -= timedelta(days=1)
    jumlah = 0
    while tanggal.isoformat() in hari:
        jumlah += 1
        tanggal -= timedelta(days=1)
    return jumlah


# ----------------------------------------------------------------- tugas rumah


def usul_tugas(status: StatusAnak, sekarang: datetime, jumlah: int = 3) -> list[dict]:
    """Memilih item untuk latihan rumah.

    Yang sudah pernah dilatih didahulukan, diurutkan dari bunyi yang paling banyak
    lupa atau paling lemah. Kalau belum cukup, diisi item baru sesuai urutan kurikulum.
    Tidak pernah melampaui tingkat yang sudah dicapai anak.
    """
    batas_tingkat = max(1, tingkat_tercapai(status))
    calon = []
    for urut, it in enumerate(ITEM):
        if (
            it.tingkat > batas_tingkat
            or not prasyarat_terpenuhi(status, it, sekarang)
            or _sudah_lewat(status, it, sekarang)
        ):
            continue
        kc = [status.kc.get((b, it.tingkat)) for b in it.bunyi]
        fokus = min(it.bunyi, key=lambda b: p_kini(status, b, it.tingkat, sekarang))
        p = p_kini(status, fokus, it.tingkat, sekarang)
        if all(k is not None and k.n > 0 for k in kc):
            turun = max(k.p - p_kini(status, b, it.tingkat, sekarang) for b, k in zip(it.bunyi, kc))
            kunci = (0, -(turun + 0.5 * (1 - p)), -it.tingkat, urut)
        else:
            kunci = (1, 0.0, it.tingkat, urut)
        calon.append((kunci, it, fokus, p))
    calon.sort(key=lambda c: c[0])

    terpilih: list[tuple] = []
    fokus_dipakai: set[str] = set()
    for putaran in (1, 2):  # putaran 2 mengisi sisa kalau bunyi fokusnya kurang beragam
        for c in calon:
            if len(terpilih) >= jumlah:
                break
            if c in terpilih or (putaran == 1 and c[2] in fokus_dipakai):
                continue
            terpilih.append(c)
            fokus_dipakai.add(c[2])

    hasil = []
    for _, it, fokus, p in terpilih:
        k = status.kc.get((fokus, it.tingkat))
        hasil.append(
            {
                "item": it.ke_dict(),
                "bunyi_fokus": fokus,
                "label": label_penguasaan(p) if k and k.n else "belum_dilatih",
                "hari_sejak_latihan": (sekarang - k.terakhir).days if k and k.terakhir else None,
            }
        )
    return hasil


def fokus_belajar(status: StatusAnak, sekarang: datetime, jumlah: int = 3) -> list[dict]:
    """Bunyi yang paling perlu dilatih, dari data anak: yang macet dulu, lalu yang
    paling banyak lupa, lalu yang penguasaannya paling rendah. Satu baris per bunyi."""
    calon = []
    macet = {(m["bunyi"], m["tingkat"]) for m in insight(status, sekarang)["macet"]}
    for (bunyi, tingkat), k in status.kc.items():
        if k.n == 0:
            continue
        p = p_kini(status, bunyi, tingkat, sekarang)
        turun = k.p - p
        if (bunyi, tingkat) in macet:
            alasan, urut = "macet", (0, p)
        elif turun >= 0.1:
            alasan, urut = "lupa", (1, -turun)
        elif p < AMBANG_SUDAH_BISA:
            alasan, urut = "lemah", (2, p)
        else:
            continue
        calon.append((urut, -tingkat, bunyi, tingkat, p, alasan))
    calon.sort()
    hasil, dipakai = [], set()
    for _, _, bunyi, tingkat, p, alasan in calon:
        if bunyi in dipakai:
            continue
        dipakai.add(bunyi)
        hasil.append({"bunyi": bunyi, "tingkat": tingkat, "label": label_penguasaan(p), "alasan": alasan})
        if len(hasil) >= jumlah:
            break
    return hasil


def tren(status: StatusAnak, sekarang: datetime, hari: int = 7) -> dict:
    """Perbandingan minggu ini dengan sebelumnya: arah kemajuan tiap bunyi dan tingkat berhasil."""
    batas = tanggal_lokal(sekarang - timedelta(days=hari))
    r = riwayat(status)
    arah = {}
    for bunyi, garis in r["per_bunyi"].items():
        lama = [g["kemajuan"] for g in garis if g["tanggal"] < batas]
        baru = [g["kemajuan"] for g in garis if g["tanggal"] >= batas]
        if lama and baru:
            beda = baru[-1] - lama[-1]
            arah[bunyi] = "naik" if beda > 0.03 else "turun" if beda < -0.03 else "tetap"
        elif baru:
            arah[bunyi] = "baru dilatih"

    def laju(daftar: list[dict]) -> float | None:
        total = sum(h["percobaan"] for h in daftar)
        return round(sum(h["berhasil"] for h in daftar) / total, 2) if total else None

    return {
        "arah_bunyi": arah,
        "berhasil_minggu_ini": laju([h for h in r["harian"] if h["tanggal"] >= batas]),
        "berhasil_sebelumnya": laju([h for h in r["harian"] if h["tanggal"] < batas]),
    }


# ------------------------------------------------------------------ lelah

LAMA_SESI_MAKS = timedelta(minutes=15)
PERCOBAAN_SESI_MAKS = 40
FAKTOR_MELAMBAT = 1.6
PENURUNAN_BERHASIL = 0.3


def _median(nilai: list[int]) -> float:
    urut = sorted(nilai)
    tengah = len(urut) // 2
    return urut[tengah] if len(urut) % 2 else (urut[tengah - 1] + urut[tengah]) / 2


def deteksi_lelah(status: StatusAnak, sekarang: datetime) -> dict:
    """Tanda anak sebaiknya berhenti untuk hari ini, dari pola sesi ini.

    - sudah berlatih 15 menit atau 40 percobaan (anak SD cepat lelah berkonsentrasi);
    - makin lambat: median waktu 5 percobaan terakhir minimal 1,6 kali 5 percobaan pertama;
    - makin sering gagal: tingkat berhasil 10 percobaan terakhir turun 30 poin dari 10 pertama.
    """
    alasan = []
    if status.sesi_mulai and sekarang - status.sesi_mulai >= LAMA_SESI_MAKS:
        alasan.append("sudah berlatih 15 menit")
    if len(status.hasil_sesi) >= PERCOBAAN_SESI_MAKS:
        alasan.append(f"sudah {len(status.hasil_sesi)} percobaan")
    d = status.durasi_sesi
    if len(d) >= 10 and _median(d[-5:]) >= FAKTOR_MELAMBAT * max(_median(d[:5]), 1):
        alasan.append("makin lama menjawab")
    h = status.hasil_sesi
    if len(h) >= 20 and sum(h[:10]) / 10 - sum(h[-10:]) / 10 >= PENURUNAN_BERHASIL:
        alasan.append("makin sering gagal dibanding awal sesi")
    return {"lelah": bool(alasan), "alasan": alasan}
