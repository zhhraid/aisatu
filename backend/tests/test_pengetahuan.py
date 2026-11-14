import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from satu_ai import mulut, otak, pengetahuan
from satu_ai.api import buat_router
from satu_ai.kurikulum import ITEM_PER_ID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skrip"))
import kumpulkan_pengetahuan as pengumpul  # noqa: E402

T0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
ISI = " ".join(["kata"] * 25)


def basis(*paragraf):
    data = {
        "sumber": [{"id": "s1", "judul": "Buku A", "url": "https://a"}, {"id": "s2", "judul": "Web B", "url": "https://b"}],
        "paragraf": [
            {"id": f"P{i}", "sumber": s, "teks": t, "bunyi": pengetahuan.tandai_bunyi(t), "pembaca": pengetahuan.tandai_pembaca(t)}
            for i, (s, t) in enumerate(paragraf, start=1)
        ],
    }
    return pengetahuan.Pengetahuan(data)


def llm_palsu(jawaban):
    async def panggil(sistem, pesan):
        panggil.pesan = json.loads(pesan)
        return jawaban

    return panggil


# ------------------------------------------------------------- pengumpul


def test_potong_menggabungkan_yang_pendek_dan_memecah_yang_panjang():
    teks = "Judul\n\n" + "Satu dua tiga. " * 5 + "\n\n" + "Latihan bibir. " * 100
    hasil = pengumpul.potong(teks)
    assert all(pengumpul.MIN_KATA <= len(p.split()) <= pengumpul.MAKS_KATA for p in hasil)
    assert hasil[0].startswith("Judul Satu dua tiga.")


def test_html_tanpa_skrip_dan_navigasi():
    html = b"<html><nav>Menu Beranda</nav><script>var x=1</script><p>Orang tua dapat <b>mendampingi</b> anak.</p></html>"
    teks = pengumpul.teks_html(html)[0][0]
    assert "mendampingi" in teks and "Menu" not in teks and "var x" not in teks


def test_hanya_paragraf_relevan_yang_disimpan_dan_ditandai():
    sumber = {"id": "s1"}
    relevan = "Latihan vokal u dilakukan dengan bibir maju ke depan bersama orang tua di rumah. " + ISI
    lain = "Harga saham naik pada kuartal ketiga karena permintaan yang kuat dari pasar. " + ISI
    hasil = pengumpul.paragraf_dari(sumber, [(relevan + "\n\n" + lain, 7)])
    assert len(hasil) == 1
    assert hasil[0]["bunyi"] == ["u"] and hasil[0]["pembaca"] == ["orang_tua"] and hasil[0]["halaman"] == 7


# ----------------------------------------------------------------- pencari


def test_cari_mengutamakan_bunyi_dan_pembaca_yang_sesuai():
    b = basis(
        ("s1", "Untuk vokal u, ajak anak memajukan bibir sambil bercermin. " + ISI),
        ("s1", "Untuk bunyi bilabial m b p, rapatkan kedua bibir. " + ISI),
        ("s2", "Orang tua dapat mendampingi anak berlatih vokal u di rumah setiap hari. " + ISI),
        ("s2", "Sejarah bahasa isyarat di berbagai negara. " + ISI),
    )
    hasil = b.cari(["u"], "orang_tua", k=2)
    assert [h["teks"][:10] for h in hasil] == ["Orang tua ", "Untuk voka"]
    assert hasil[0]["judul"] == "Web B" and hasil[0]["url"] == "https://b"
    assert b.cari(["M"], "guru", k=1)[0]["teks"].startswith("Untuk bunyi bilabial")


def test_cari_paling_banyak_k_rujukan():
    b = basis(*[("s1", f"Latihan vokal a nomor {i}. " + ISI) for i in range(5)])
    assert len(b.cari(["a"], "guru", k=3)) == 3


def test_bobot_sumber_mendahulukan_buku_dan_pengisi_lemah_dibuang():
    data = {
        "sumber": [{"id": "s1", "judul": "Buku", "bobot": 1.5}, {"id": "s2", "judul": "Ensiklopedia", "bobot": 0.5}],
        "paragraf": [
            {"id": "P1", "sumber": "s2", "teks": "Vokal u adalah vokal belakang tertutup bundar. " + ISI, "bunyi": ["u"], "pembaca": []},
            {"id": "P2", "sumber": "s1", "teks": "Latih vokal u dengan bibir maju di depan cermin. " + ISI, "bunyi": ["u"], "pembaca": ["guru"]},
            {"id": "P3", "sumber": "s2", "teks": "Sejarah singkat sekolah dan bicara umum. " + ISI, "bunyi": [], "pembaca": []},
        ],
    }
    hasil = pengetahuan.Pengetahuan(data).cari(["u"], "guru", k=3)
    # Buku jauh lebih kuat; ensiklopedia dan paragraf umum jatuh di bawah seperempat skornya.
    assert [h["judul"] for h in hasil] == ["Buku"]
    tanpa_buku = pengetahuan.Pengetahuan({**data, "paragraf": [data["paragraf"][0], data["paragraf"][2]]})
    assert [h["teks"][:5] for h in tanpa_buku.cari(["u"], "guru", k=3)] == ["Vokal"]


def test_pembaca_tata_letak_menyusun_teks_dan_membersihkannya(tmp_path):
    def teks(x, y, isi):
        return {"type": "text", "x": x, "y": y, "height": 16, "fontSize": 13, "text": isi}

    halaman = [
        {"children": [teks(50, 900, "Panduan Guru Pengembangan Wicara  bagi Peserta Didik dengan Hambatan Pendengaran 42"),
                      teks(50, 120, "dengan bibir."), teks(50, 100, "Orang tua melatih <span style='x'>vokal</span> u"),
                      {"type": "group", "x": 10, "y": 300, "children": [teks(40, 0, "hambatan ȑsik &amp; Ȓeksibel")]},
                      teks(300, 920, "untuk SDLB, SMPLB, SMALB")]},
    ]
    berkas = tmp_path / "buku.json"
    berkas.write_text(json.dumps({"pages": [{}] * 18 + halaman}), encoding="utf-8")
    sumber = {"halaman": [19, 19], "geser_halaman": 18,
              "buang": r"Panduan Guru Pengembangan Wicara\s+bagi Peserta Didik dengan Hambatan Pendengaran( \d+)?|untuk SDLB, SMPLB, SMALB|\d{1,3}"}
    [(isi, nomor)] = pengumpul.teks_tata_letak(berkas, sumber)
    assert nomor == 1  # halaman cetak = halaman berkas dikurangi 18
    assert isi == "Orang tua melatih vokal u\ndengan bibir.\n\nhambatan fisik & fleksibel"


def test_basis_yang_disertakan_berisi_buku_panduan():
    b = pengetahuan.muat()
    assert "kemdikbud-wicara-2024" in b.sumber
    rujukan = b.cari(["M"], "guru", k=3)
    assert rujukan and all(r["judul"].startswith("Panduan Guru Pengembangan Wicara") for r in rujukan)
    assert all(isinstance(r["halaman"], int) for r in rujukan)


def test_basis_kosong_tidak_membuat_galat(tmp_path):
    kosong = pengetahuan.muat.__wrapped__(tmp_path / "tidak-ada.json")
    assert len(kosong) == 0 and kosong.cari(["a"], "guru") == []


def test_basis_yang_disertakan_terbaca():
    b = pengetahuan.muat()
    assert len(b) > 0 and all(p["sumber"] in b.sumber for p in b.paragraf)


# ------------------------------------------------------------ laporan + rujukan

DATA = {"sudah_bisa": [{"bunyi": "a", "tingkat": 2}], "sedang_dilatih": [{"bunyi": "u", "tingkat": 2}],
        "hari_latihan": 3, "tips": "Latihan di depan cermin."}
RUJ = [{"teks": "Ajak anak memajukan bibir untuk vokal u. " + ISI, "judul": "Buku A", "url": "https://a", "halaman": 12}]
LAPORAN = {"sudah_bisa": "ANAK sudah bisa bunyi a.", "sedang_dilatih": "ANAK berlatih bunyi u.",
           "cara_membantu": "Ajak ANAK memajukan bibir di depan cermin."}


def test_laporan_menyertakan_sumber_yang_dirujuk():
    palsu = llm_palsu({**LAPORAN, "rujukan": ["R1"]})
    hasil = asyncio.run(mulut.laporan_mingguan(DATA, "Sinta", palsu, rujukan=RUJ))
    assert hasil["sumber"] == "llm"
    assert hasil["rujukan"] == [{"judul": "Buku A", "url": "https://a", "halaman": 12}]
    assert palsu.pesan["rujukan"][0]["kode"] == "R1"
    assert len(palsu.pesan["rujukan"][0]["isi"].split()) <= 110  # dipotong supaya hemat


def test_laporan_yang_menyebut_rujukan_karangan_jatuh_ke_templat():
    hasil = asyncio.run(mulut.laporan_mingguan(DATA, "Sinta", llm_palsu({**LAPORAN, "rujukan": ["R9"]}), rujukan=RUJ))
    assert hasil["sumber"] == "templat" and hasil["rujukan"] == []


def test_laporan_boleh_hanya_memakai_tips():
    hasil = asyncio.run(mulut.laporan_mingguan(DATA, "Sinta", llm_palsu({**LAPORAN, "rujukan": ["TIPS"]}), rujukan=RUJ))
    assert hasil["sumber"] == "llm" and hasil["rujukan"] == []


# --------------------------------------------------------------- saran belajar

FOKUS = [{"bunyi": "u", "tingkat": 2, "label": "sedang_dilatih", "alasan": "macet"},
         {"bunyi": "o", "tingkat": 1, "label": "hampir_bisa", "alasan": "lupa"}]


def test_saran_dari_llm_dengan_rujukan_dan_data():
    jawab = {"saran": [
        {"teks": "Latih ANAK memajukan bibir untuk bunyi u selama 5 menit.", "rujukan": ["R1"]},
        {"teks": "Ulangi bunyi o karena mulai menurun.", "rujukan": ["DATA"]},
    ]}
    hasil = asyncio.run(mulut.saran_belajar(FOKUS, "Sinta", RUJ, llm_palsu(jawab)))
    assert hasil["sumber"] == "llm"
    assert hasil["saran"][0] == {"teks": "Latih Sinta memajukan bibir untuk bunyi u selama 5 menit.",
                                 "rujukan": [{"judul": "Buku A", "url": "https://a", "halaman": 12}]}
    assert hasil["saran"][1]["rujukan"] == []


@pytest.mark.parametrize("rusak", [
    None,
    {"saran": []},
    {"saran": [{"teks": "Sudah 80% bisa.", "rujukan": ["DATA"]}]},
    {"saran": [{"teks": "Latihan tanpa dasar.", "rujukan": []}]},
    {"saran": [{"teks": "Rujukan karangan.", "rujukan": ["R7"]}]},
])
def test_saran_yang_tidak_berdasar_jatuh_ke_templat_dari_data(rusak):
    hasil = asyncio.run(mulut.saran_belajar(FOKUS, "Sinta", RUJ, llm_palsu(rusak)))
    assert hasil["sumber"] == "templat"
    assert hasil["saran"][0]["teks"].startswith("Bunyi u belum naik meski sudah sering dicoba.")
    assert "bulatkan bibir" in hasil["saran"][1]["teks"]


def test_fokus_belajar_macet_lalu_lupa_lalu_lemah():
    s = otak.StatusAnak()
    for _ in range(6):
        otak.catat_percobaan(s, ITEM_PER_ID["t1-u"], False, 0, T0)
    lama = T0 - timedelta(days=40)
    for _ in range(4):
        otak.catat_percobaan(s, ITEM_PER_ID["t1-o"], True, 1, lama)
    otak.catat_percobaan(s, ITEM_PER_ID["t1-a"], True, 1, T0)
    for _ in range(4):
        otak.catat_percobaan(s, ITEM_PER_ID["t1-i"], True, 1, T0)  # tuntas: tidak perlu
    fokus = otak.fokus_belajar(s, T0)
    assert [(f["bunyi"], f["alasan"]) for f in fokus] == [("u", "macet"), ("o", "lupa"), ("a", "lemah")]


def test_endpoint_saran_belajar(monkeypatch):
    for kunci in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(kunci, raising=False)
    app = FastAPI()
    app.include_router(buat_router(demo=True))
    k = TestClient(app)
    k.post("/ai/demo/isi", json={"anak_id": "sinta", "profil": "menengah"})
    hasil = k.post("/ai/anak/sinta/saran-belajar", json={"nama": "Sinta"}).json()
    assert hasil["sumber"] == "templat" and hasil["fokus"][0]["bunyi"] == "u"
    assert hasil["saran"] and all(s["teks"] for s in hasil["saran"])
    laporan = k.post("/ai/anak/sinta/laporan-mingguan", json={"nama": "Sinta"}).json()
    assert laporan["rujukan"] == []  # templat tidak menyebut rujukan


@pytest.mark.parametrize("kotor, bersih", [
    ("Ajak ANAK bercermin agar posisi bibir lebih tepat sesuai R3.", "Ajak ANAK bercermin agar posisi bibir lebih tepat."),
    ("Latih bunyi /u/ dengan benda konkret berdasarkan DATA.", "Latih bunyi /u/ dengan benda konkret."),
    ("Gunakan kartu gambar (R1) setiap hari.", "Gunakan kartu gambar setiap hari."),
    ("Menurut rujukan R2, latihan dimulai dari pelemasan.", "Latihan dimulai dari pelemasan."),
    ("Pakai tips TIPS, duduk berhadapan.", "Pakai tips, duduk berhadapan."),
    ("Catat data latihan dan beri tips singkat.", "Catat data latihan dan beri tips singkat."),
    ("Ulangi bunyi a di Rumah.", "Ulangi bunyi a di Rumah."),
])
def test_kode_rujukan_dibuang_dari_kalimat(kotor, bersih):
    assert mulut.buang_kode(kotor) == bersih


def test_saran_dari_llm_tanpa_kode_di_kalimat():
    jawab = {"saran": [
        {"teks": "Ajak ANAK melatih bunyi /i/ dengan cermin sesuai R1.", "rujukan": ["R1"]},
        {"teks": "Latih bunyi /u/ dengan benda konkret berdasarkan DATA.", "rujukan": ["DATA"]},
    ]}
    hasil = asyncio.run(mulut.saran_belajar(FOKUS, "Sinta", RUJ, llm_palsu(jawab)))
    assert [s["teks"] for s in hasil["saran"]] == [
        "Ajak Sinta melatih bunyi /i/ dengan cermin.",
        "Latih bunyi /u/ dengan benda konkret.",
    ]
