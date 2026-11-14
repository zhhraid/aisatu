"""Endpoint lapis AI. Pasang ke aplikasi FastAPI utama dengan:

    app.include_router(buat_router(penyimpanan))

Login dan pengecekan hak akses (guru hanya kelasnya, orang tua hanya anaknya)
belum ada di sini; tambahkan sebagai dependency saat router dipasang.
"""

from __future__ import annotations

import os
import random
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from typing import Literal

from pydantic import BaseModel, Field

from . import llm, mulut, otak, pengaturan, pengetahuan
from .kurikulum import (
    BUNYI,
    ITEM,
    ITEM_PER_ID,
    NAMA_TINGKAT,
    PARAM,
    TEKS_LABEL,
    TIPS_PENDAMPING,
    WARNA_LABEL,
)
from .penyimpanan import Penyimpanan, PenyimpananMemori


class MasukanPercobaan(BaseModel):
    item_id: str
    berhasil: bool
    langkah_tercapai: int = Field(default=0, ge=0)
    durasi_ms: int | None = Field(default=None, ge=0)


class MasukanNama(BaseModel):
    nama: str = Field(min_length=1, max_length=40)


class AnakKelas(BaseModel):
    anak_id: str
    nama: str = Field(min_length=1, max_length=40)


class MasukanTanya(BaseModel):
    nama: str = Field(min_length=1, max_length=40)
    pertanyaan: str = Field(min_length=3, max_length=300)
    pembaca: Literal["guru", "orang_tua"] = "orang_tua"


class MasukanKelas(BaseModel):
    anak: list[AnakKelas]


class MasukanDemo(BaseModel):
    anak_id: str
    profil: str = "menengah"


# Yang dianggap baru tercapai minggu ini di tiap profil; sisanya tercapai lebih lama.
_BARU_TERCAPAI = {"pemula": set(), "menengah": {"a:2"}, "mahir": {"a:4", "M:4"}}

# Profil data demo: penguasaan per "bunyi:tingkat". Selalu ditandai sintetis.
_PROFIL_DEMO: dict[str, dict[str, tuple[float, int, int]]] = {
    # nilai = (penguasaan, jumlah percobaan, hari sejak latihan terakhir)
    "pemula": {"a:1": (0.72, 1, 0)},
    "menengah": {
        "a:1": (0.98, 4, 1), "i:1": (0.98, 4, 1), "u:1": (0.97, 5, 1),
        "o:1": (0.96, 5, 2), "M:1": (0.98, 3, 2),
        "a:2": (0.96, 4, 1), "i:2": (0.90, 4, 5), "u:2": (0.35, 7, 1),
    },
    "mahir": {
        **{f"{b}:{t}": (0.97, 5, 3 + t) for b in BUNYI for t in (1, 2, 3)},
        "a:4": (0.90, 4, 6), "M:4": (0.88, 4, 6), "o:4": (0.55, 3, 2),
    },
}


def buat_router(penyimpanan: Penyimpanan | None = None, demo: bool | None = None) -> APIRouter:
    """demo=True: pemilihan tanpa acak dan endpoint pengisi data demo aktif."""
    simpanan = penyimpanan or PenyimpananMemori()
    mode_demo = os.getenv("SATU_DEMO") == "1" if demo is None else demo
    rng = None if mode_demo else random.Random()
    router = APIRouter(prefix="/ai", tags=["ai"])

    def item_atau_404(item_id: str):
        item = ITEM_PER_ID.get(item_id)
        if item is None:
            raise HTTPException(404, f"Item latihan tidak dikenal: {item_id}")
        return item

    def ringkas_peta(status: otak.StatusAnak, sekarang) -> list[dict]:
        baris = otak.peta(status, sekarang)
        for b in baris:
            b["teks_label"] = TEKS_LABEL[b["label"]]
            b["warna"] = WARNA_LABEL[b["label"]]
        return baris

    @router.get("/status")
    def status_layanan() -> dict:
        return {
            "llm_tersedia": llm.tersedia(),
            "llm_kurang": llm.kurang(),  # nama pengaturan yang belum diisi
            "berkas_env": pengaturan.STATUS["berkas_env"],
            "paragraf_rujukan": len(pengetahuan.muat()),
            "mode_demo": mode_demo,
        }

    @router.get("/kurikulum")
    def kurikulum() -> dict:
        return {
            "bunyi": list(BUNYI),
            "tingkat": [{"tingkat": t, "nama": n} for t, n in NAMA_TINGKAT.items()],
            "parameter": {t: vars(p) for t, p in PARAM.items()},
            "item": [it.ke_dict() for it in ITEM],
        }

    @router.post("/anak/{anak_id}/sesi")
    def mulai_sesi(anak_id: str) -> dict:
        status = simpanan.muat(anak_id)
        otak.mulai_sesi(status)
        simpanan.simpan(anak_id, status)
        pilihan = otak.pilih_berikutnya(status, otak.sekarang_utc(), rng)
        return {"berikutnya": pilihan.ke_dict()}

    @router.get("/anak/{anak_id}/berikutnya")
    def berikutnya(anak_id: str) -> dict:
        status = simpanan.muat(anak_id)
        return otak.pilih_berikutnya(status, otak.sekarang_utc(), rng).ke_dict()

    @router.post("/anak/{anak_id}/percobaan")
    def percobaan(anak_id: str, masukan: MasukanPercobaan) -> dict:
        item = item_atau_404(masukan.item_id)
        sekarang = otak.sekarang_utc()
        status = simpanan.muat(anak_id)
        perubahan = otak.catat_percobaan(
            status, item, masukan.berhasil, masukan.langkah_tercapai, sekarang
        )
        simpanan.simpan(anak_id, status)
        return {
            "perubahan": perubahan,
            "tingkat_berhasil": otak.tingkat_berhasil(status),
            "streak": otak.streak(status, sekarang),
            "berikutnya": otak.pilih_berikutnya(status, sekarang, rng).ke_dict(),
        }

    @router.get("/anak/{anak_id}/peta")
    def peta(anak_id: str) -> dict:
        sekarang = otak.sekarang_utc()
        status = simpanan.muat(anak_id)
        return {
            "bunyi": ringkas_peta(status, sekarang),
            "insight": otak.insight(status, sekarang),
            "tingkat_berhasil": otak.tingkat_berhasil(status),
            "hari_latihan_minggu_ini": otak.hari_latihan_minggu_ini(status, sekarang),
            "streak": otak.streak(status, sekarang),
            "level": otak.status_level(status, sekarang),
            "sintetis": status.sintetis,
        }

    @router.post("/anak/{anak_id}/tugas-usulan")
    async def tugas_usulan(anak_id: str, masukan: MasukanNama) -> dict:
        status = simpanan.muat(anak_id)
        usulan = otak.usul_tugas(status, otak.sekarang_utc())
        hasil = await mulut.alasan_tugas(usulan, masukan.nama)
        for t in hasil["tugas"]:
            t["teks_label"] = TEKS_LABEL[t["label"]]
        return hasil

    @router.post("/anak/{anak_id}/laporan-mingguan")
    async def laporan_mingguan(anak_id: str, masukan: MasukanNama) -> dict:
        sekarang = otak.sekarang_utc()
        status = simpanan.muat(anak_id)
        baris = otak.peta(status, sekarang)
        minggu = sekarang.isocalendar().week
        data = {
            "sudah_bisa": [
                {"bunyi": b["bunyi"], "tingkat": b["tingkat_tuntas"]} for b in baris if b["tingkat_tuntas"]
            ],
            "sedang_dilatih": [
                {"bunyi": b["bunyi"], "tingkat": b["tingkat"]}
                for b in baris
                if b["tingkat"] and b["label"] != "sudah_bisa"
            ],
            "hari_latihan": otak.hari_latihan_minggu_ini(status, sekarang),
            "tips": TIPS_PENDAMPING[minggu % len(TIPS_PENDAMPING)],
        }
        dilatih = [d["bunyi"] for d in data["sedang_dilatih"]]
        rujukan = pengetahuan.muat().cari(dilatih, "orang_tua", k=3)
        return await mulut.laporan_mingguan(data, masukan.nama, rujukan=rujukan)

    @router.get("/anak/{anak_id}/level")
    def level(anak_id: str) -> dict:
        """Peta petualangan: enam level dengan kemajuan, bintang, dan status."""
        return otak.status_level(simpanan.muat(anak_id), otak.sekarang_utc())

    @router.get("/anak/{anak_id}/riwayat")
    def riwayat(anak_id: str) -> dict:
        """Perkembangan harian dan kemajuan tiap bunyi dari waktu ke waktu (untuk grafik)."""
        return otak.riwayat(simpanan.muat(anak_id))

    @router.post("/anak/{anak_id}/tanya")
    async def tanya(anak_id: str, masukan: MasukanTanya) -> dict:
        """Agent tanya progres: menjawab pertanyaan guru atau orang tua dari data anak."""
        sekarang = otak.sekarang_utc()
        status = simpanan.muat(anak_id)
        baris = otak.peta(status, sekarang)
        lv = otak.status_level(status, sekarang)
        nomor = lv["level_sekarang"]
        nama_lv = next(x["nama"] for x in lv["level"] if x["level"] == nomor)
        fokus = otak.fokus_belajar(status, sekarang)
        t = otak.tren(status, sekarang)
        nama_b = mulut.nama_bunyi
        data = {
            "level": {"nomor": nomor, "nama": nama_lv},
            "level_tuntas": [x["level"] for x in lv["level"] if x["status"] == "tuntas"],
            "sudah_bisa": [nama_b(b["bunyi"]) for b in baris if b["tingkat_tuntas"]],
            "sedang_dilatih": [nama_b(b["bunyi"]) for b in baris if b["tingkat"] and b["label"] != "sudah_bisa"],
            "perlu_perhatian": [nama_b(f["bunyi"]) for f in fokus],
            "alasan_perhatian": {nama_b(f["bunyi"]): f["alasan"] for f in fokus},
            "tren_bunyi": {nama_b(b): arah for b, arah in t["arah_bunyi"].items()},
            "keberhasilan_minggu_ini": (
                None if t["berhasil_minggu_ini"] is None
                else "tinggi" if t["berhasil_minggu_ini"] >= 0.8
                else "cukup" if t["berhasil_minggu_ini"] >= 0.6 else "rendah"
            ),
            "hari_latihan_minggu_ini": otak.hari_latihan_minggu_ini(status, sekarang),
            "streak": otak.streak(status, sekarang),
        }
        pembaca = masukan.pembaca
        rujukan = pengetahuan.muat().cari([f["bunyi"] for f in fokus], pembaca, k=3)
        hasil = await mulut.tanya_progres(masukan.pertanyaan, data, masukan.nama, pembaca, rujukan)
        return {**hasil, "data": data}

    @router.post("/anak/{anak_id}/saran-belajar")
    async def saran_belajar(anak_id: str, masukan: MasukanNama) -> dict:
        """Saran belajar untuk guru: dari data latihan anak dan rujukan yang dikumpulkan."""
        sekarang = otak.sekarang_utc()
        fokus = otak.fokus_belajar(simpanan.muat(anak_id), sekarang)
        rujukan = pengetahuan.muat().cari([f["bunyi"] for f in fokus], "guru", k=3)
        hasil = await mulut.saran_belajar(fokus, masukan.nama, rujukan)
        return {"fokus": fokus, **hasil}

    @router.post("/kelas/ringkasan")
    async def ringkasan_kelas(masukan: MasukanKelas) -> dict:
        sekarang = otak.sekarang_utc()
        daftar = []
        for a in masukan.anak:
            temuan = otak.insight(simpanan.muat(a.anak_id), sekarang)
            daftar.append(
                {
                    "nama": a.nama,
                    "macet": list(dict.fromkeys(x["bunyi"] for x in temuan["macet"])),
                    "naik": list(dict.fromkeys(x["bunyi"] for x in temuan["naik"])),
                }
            )
        return await mulut.ringkasan_kelas(daftar)

    if mode_demo:

        @router.post("/demo/isi")
        def isi_demo(masukan: MasukanDemo) -> dict:
            """Mengisi satu anak dengan data buatan untuk demo. Ditandai sintetis."""
            profil = _PROFIL_DEMO.get(masukan.profil)
            if profil is None:
                raise HTTPException(404, f"Profil tidak dikenal. Pilihan: {sorted(_PROFIL_DEMO)}")
            sekarang = otak.sekarang_utc()
            status = otak.StatusAnak(sintetis=True)
            for kunci, (p, n, hari) in profil.items():
                bunyi, tingkat = kunci.split(":")
                waktu = sekarang - timedelta(days=hari)
                tercapai = None
                if p >= 0.85:
                    baru = kunci in _BARU_TERCAPAI[masukan.profil]
                    tercapai = waktu if baru else waktu - timedelta(days=21)
                status.kc[(bunyi, int(tingkat))] = otak.KC(
                    p=p, n=n, terakhir=waktu, tercapai_pada=tercapai, tuntas=p >= 0.95
                )
                status.hari_latihan.append(otak.tanggal_lokal(waktu))
            status.hari_latihan = sorted(set(status.hari_latihan))
            # Riwayat buatan: penguasaan naik bertahap dalam dua minggu terakhir.
            for kunci, (p, n, hari) in profil.items():
                bunyi, tingkat = kunci.split(":")
                for mundur, faktor in ((hari + 14, 0.45), (hari + 7, 0.75), (hari, 1.0)):
                    tanggal = otak.tanggal_lokal(sekarang - timedelta(days=mundur))
                    otak.catat_riwayat(status, tanggal, faktor > 0.6, {(bunyi, int(tingkat)): p * faktor})
            simpanan.simpan(masukan.anak_id, status)
            return {"anak_id": masukan.anak_id, "profil": masukan.profil, "sintetis": True}

    return router
