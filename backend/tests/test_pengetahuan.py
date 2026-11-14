import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from satu_ai import llm, mulut, otak, pengetahuan
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
    assert b.cari(["m"], "guru", k=1)[0]["teks"].startswith("Untuk bunyi bilabial")


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
    rujukan = b.cari(["m"], "guru", k=3)
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
        {"bunyi": "u", "teks": "Latih ANAK memajukan bibir untuk bunyi u selama 5 menit.", "rujukan": ["R1"]},
        {"bunyi": "o", "teks": "Ulangi bunyi o karena mulai menurun.", "rujukan": ["DATA"]},
    ]}
    hasil = asyncio.run(mulut.saran_belajar(FOKUS, "Sinta", RUJ, llm_palsu(jawab)))
    assert hasil["sumber"] == "llm"
    assert hasil["saran"][0] == {"bunyi": "u", "teks": "Latih Sinta memajukan bibir untuk bunyi u selama 5 menit.",
                                 "rujukan": [{"judul": "Buku A", "url": "https://a", "halaman": 12}]}
    assert hasil["saran"][1]["rujukan"] == []


@pytest.mark.parametrize("rusak", [
    None,
    {"saran": []},
    {"saran": [{"bunyi": "u", "teks": "Sudah 80% bisa.", "rujukan": ["DATA"]}, {"bunyi": "o", "teks": "Ulangi o.", "rujukan": ["DATA"]}]},
    {"saran": [{"bunyi": "u", "teks": "Latihan tanpa dasar.", "rujukan": []}, {"bunyi": "o", "teks": "Ulangi o.", "rujukan": ["DATA"]}]},
    {"saran": [{"bunyi": "u", "teks": "Rujukan karangan.", "rujukan": ["R7"]}, {"bunyi": "o", "teks": "Ulangi o.", "rujukan": ["DATA"]}]},
    # Gemini memilih huruf sendiri atau mengubah urutan: ditolak.
    {"saran": [{"bunyi": "e", "teks": "Latih bunyi e.", "rujukan": ["DATA"]}, {"bunyi": "o", "teks": "Ulangi o.", "rujukan": ["DATA"]}]},
    {"saran": [{"bunyi": "o", "teks": "Ulangi o.", "rujukan": ["DATA"]}, {"bunyi": "u", "teks": "Latih u.", "rujukan": ["DATA"]}]},
    {"saran": [{"bunyi": "u", "teks": "Latih u.", "rujukan": ["DATA"]}]},
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
        {"bunyi": "u", "teks": "Ajak ANAK melatih bunyi /u/ dengan cermin sesuai R1.", "rujukan": ["R1"]},
        {"bunyi": "o", "teks": "Latih bunyi /o/ dengan benda konkret berdasarkan DATA.", "rujukan": ["DATA"]},
    ]}
    hasil = asyncio.run(mulut.saran_belajar(FOKUS, "Sinta", RUJ, llm_palsu(jawab)))
    assert [s["teks"] for s in hasil["saran"]] == [
        "Ajak Sinta melatih bunyi /u/ dengan cermin.",
        "Latih bunyi /o/ dengan benda konkret.",
    ]


# ------------------------------------------------------------- agent tanya progres

DATA_TANYA = {
    "level": {"nomor": 2, "nama": "Vokal e, o"}, "level_tuntas": [1],
    "sudah_bisa": ["a", "i"], "sedang_dilatih": ["u", "o"], "perlu_perhatian": ["u"],
    "alasan_perhatian": {"u": "macet"}, "tren_bunyi": {"u": "tetap"},
    "keberhasilan_minggu_ini": "cukup", "hari_latihan_minggu_ini": 3, "streak": 2,
}


def test_tanya_dijawab_dari_data_dengan_rujukan_dan_nama_tidak_dikirim():
    jawab = {"jawaban": "ANAK sudah bisa a dan i, dan sudah berlatih 2 hari berturut-turut. Bunyi u perlu dilatih dengan bibir maju (R1).", "rujukan": ["R1"]}
    palsu = llm_palsu(jawab)
    hasil = asyncio.run(mulut.tanya_progres("Sinta lemah di mana?", DATA_TANYA, "Sinta", "orang_tua", RUJ, palsu))
    assert hasil["sumber"] == "llm"
    assert hasil["jawaban"].startswith("Sinta sudah bisa a dan i") and "R1" not in hasil["jawaban"]
    assert hasil["rujukan"] == [{"judul": "Buku A", "url": "https://a", "halaman": 12}]
    assert palsu.pesan["pertanyaan"] == "ANAK lemah di mana?"  # nama tidak dikirim ke LLM
    assert "Sinta" not in json.dumps(palsu.pesan)


def test_tanya_di_luar_topik_boleh_ditolak_tanpa_rujukan():
    jawab = {"jawaban": "Maaf, saya tidak bisa menjawab soal obat. Silakan tanyakan ke guru atau terapis wicara.", "rujukan": []}
    hasil = asyncio.run(mulut.tanya_progres("Obat apa untuk telinganya?", DATA_TANYA, "Sinta", "orang_tua", RUJ, llm_palsu(jawab)))
    assert hasil["sumber"] == "llm" and hasil["rujukan"] == []


@pytest.mark.parametrize("rusak", [
    None,
    {"jawaban": "Penguasaannya 45%.", "rujukan": ["DATA"]},
    {"jawaban": "Kata buku menyebut begitu.", "rujukan": ["R5"]},
    {"jawaban": "kata " * 95, "rujukan": ["DATA"]},
])
def test_tanya_yang_tidak_lolos_pagar_jatuh_ke_ringkasan_templat(rusak):
    hasil = asyncio.run(mulut.tanya_progres("Bagaimana perkembangannya?", DATA_TANYA, "Sinta", "guru", RUJ, llm_palsu(rusak)))
    assert hasil["sumber"] == "templat"
    assert hasil["jawaban"] == (
        "Sinta sekarang di Level 2 (Vokal e, o). Sudah bisa: bunyi a dan i. Sedang dilatih: bunyi u dan o. "
        "Perlu perhatian: bunyi u. Sudah berlatih 2 hari berturut-turut."
    )


def test_tren_minggu_ini_dibanding_sebelumnya():
    s = otak.StatusAnak()
    lama = T0 - timedelta(days=10)
    otak.catat_percobaan(s, ITEM_PER_ID["t1-u"], False, 0, lama)
    for _ in range(3):
        otak.catat_percobaan(s, ITEM_PER_ID["t1-u"], True, 1, T0)
    otak.catat_percobaan(s, ITEM_PER_ID["t1-a"], True, 1, T0)
    t = otak.tren(s, T0)
    assert t["arah_bunyi"] == {"u": "naik", "a": "baru dilatih"}
    assert (t["berhasil_minggu_ini"], t["berhasil_sebelumnya"]) == (1.0, 0.0)


def test_endpoint_level_riwayat_dan_tanya(monkeypatch):
    for kunci in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(kunci, raising=False)
    app = FastAPI()
    app.include_router(buat_router(demo=True))
    k = TestClient(app)
    k.post("/ai/demo/isi", json={"anak_id": "sinta", "profil": "menengah"})

    level = k.get("/ai/anak/sinta/level").json()
    assert level["level_sekarang"] == 1 and len(level["level"]) == 6
    assert level == k.get("/ai/anak/sinta/peta").json()["level"]

    riwayat = k.get("/ai/anak/sinta/riwayat").json()
    garis = riwayat["per_bunyi"]["a"]
    assert len(garis) >= 3 and garis[-1]["kemajuan"] > garis[0]["kemajuan"]  # data demo naik

    jawab = k.post("/ai/anak/sinta/tanya", json={"nama": "Sinta", "pertanyaan": "Sinta lemah di mana?", "pembaca": "guru"}).json()
    assert jawab["sumber"] == "templat" and jawab["jawaban"].startswith("Sinta sekarang di Level 1")
    assert "u" in jawab["data"]["perlu_perhatian"]
    # Bunyi yang sudah bisa di tahap bawah tapi masih dilatih di tahap atas disebut dengan tahapnya.
    assert "u (tahap bunyi tunggal dengan bantuan gambar)" in jawab["data"]["sudah_bisa"]
    assert "u (tahap bunyi tunggal)" in jawab["data"]["sedang_dilatih"]
    assert "Sudah bisa: bunyi a (tahap bunyi tunggal)" in jawab["jawaban"]
    tolak = k.post("/ai/anak/sinta/tanya", json={"nama": "Sinta", "pertanyaan": "x", "pembaca": "guru"})
    assert tolak.status_code == 422  # pertanyaan terlalu pendek


def test_model_bibir_disimpan_dan_dimuat_per_anak(monkeypatch):
    app = FastAPI()
    app.include_router(buat_router(demo=True))
    k = TestClient(app)
    assert k.get("/ai/anak/sinta/model-bibir").json() == {"model": None}
    model = {"versi": 1, "kelas": ["a", "u"], "pusat": [[0.3, 0, 0, 0, 0.5, 0], [0.03, 0.4, 0, 0, 0.1, 0]],
             "skala": [0.05] * 6, "jumlah": [30, 30], "akurasi": 0.93}
    assert k.put("/ai/anak/sinta/model-bibir", json={"model": model}).json() == {"tersimpan": True, "kelas": ["a", "u"]}
    assert k.get("/ai/anak/sinta/model-bibir").json()["model"] == model
    # Model rusak atau kelas asing ditolak.
    assert k.put("/ai/anak/sinta/model-bibir", json={"model": {**model, "kelas": ["a", "zz"]}}).status_code == 422
    assert k.put("/ai/anak/sinta/model-bibir", json={"model": {**model, "skala": [0.05] * 3}}).status_code == 422
    assert k.put("/ai/anak/sinta/model-bibir", json={"model": {**model, "versi": 2}}).status_code == 422
    # Menyimpan model tidak mengubah penguasaan anak.
    assert k.get("/ai/anak/sinta/peta").json()["hari_latihan_minggu_ini"] == 0


def test_klien_llm_memakai_suhu_rendah_supaya_konsisten(monkeypatch):
    import httpx

    terkirim = {}

    def penangan(permintaan):
        terkirim.update(json.loads(permintaan.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setenv("LLM_BASE_URL", "https://llm.contoh/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.delenv("LLM_SUHU", raising=False)
    asli = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: asli(transport=httpx.MockTransport(penangan), **kw))
    asyncio.run(llm.panggil_json("aturan", "data"))
    assert terkirim["temperature"] == 0.2


def test_usulan_dan_fokus_saran_sama_bila_data_sama(monkeypatch):
    for kunci in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(kunci, raising=False)
    app = FastAPI()
    app.include_router(buat_router(demo=False))  # mode biasa, dengan pemilihan acak
    k = TestClient(app)
    for i in range(3):
        k.post(f"/ai/anak/sinta/percobaan", json={"item_id": "t1-u", "berhasil": i == 2})
    tugas = {tuple(t["item"]["id"] for t in k.post("/ai/anak/sinta/tugas-usulan", json={"nama": "s"}).json()["tugas"]) for _ in range(5)}
    fokus = {tuple(f["bunyi"] for f in k.post("/ai/anak/sinta/saran-belajar", json={"nama": "s"}).json()["fokus"]) for _ in range(5)}
    assert len(tugas) == 1 and len(fokus) == 1


def test_data_lama_berkode_huruf_besar_tetap_terbaca():
    lama = {"kc": {"M:1": {"p": 0.9, "n": 3}, "a:1": {"p": 0.5, "n": 1}},
            "model_bibir": {"versi": 1, "kelas": ["a", "M"], "pusat": [[0.3], [0.0]], "skala": [0.05]}}
    s = otak.StatusAnak.dari_dict(lama)
    assert ("m", 1) in s.kc and ("M", 1) not in s.kc
    assert s.model_bibir["kelas"] == ["a", "m"]
    app = FastAPI()
    app.include_router(buat_router(demo=True))
    k = TestClient(app)
    model = {"versi": 1, "kelas": ["a", "M"], "pusat": [[0.3, 0], [0.0, 0]], "skala": [0.05, 0.05], "jumlah": [5, 5]}
    assert k.put("/ai/anak/x/model-bibir", json={"model": model}).json()["kelas"] == ["a", "m"]


def test_semua_kode_bunyi_huruf_kecil():
    from satu_ai.kurikulum import BUNYI, ITEM
    assert all(b == b.lower() for b in BUNYI)
    assert all(b == b.lower() for it in ITEM for b in it.urutan)
    assert all(b == b.lower() for p in pengetahuan.muat().paragraf for b in p["bunyi"])
