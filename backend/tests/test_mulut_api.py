import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from satu_ai import llm, mulut, otak
from satu_ai.api import buat_router
from satu_ai.kurikulum import ITEM_PER_ID

T0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


def llm_palsu(jawaban):
    async def panggil(sistem, pesan):
        return jawaban

    return panggil


def usulan_contoh():
    s = otak.StatusAnak()
    for b in ("a", "i", "u", "o", "M"):
        for _ in range(3):
            otak.catat_percobaan(s, ITEM_PER_ID[f"t1-{b}"], True, 1, T0)
            otak.catat_percobaan(s, ITEM_PER_ID[f"t2-{b}"], True, 1, T0)
    otak.catat_percobaan(s, ITEM_PER_ID["t3-mu"], False, 1, T0)
    return otak.usul_tugas(s, T0)


# ---------------------------------------------------------------------- pagar


def test_pagar_menolak_angka_panjang_dan_kata_latihan_lain():
    assert mulut.periksa_teks("Bunyi u perlu diulang.", 20, {"mu"}) is None
    assert mulut.periksa_teks("Sudah 80 persen.", 20) == "memuat angka"
    assert mulut.periksa_teks("kata " * 21, 20) == "terlalu panjang"
    assert mulut.periksa_teks("", 20) == "kosong"
    assert mulut.periksa_teks(None, 20) == "kosong"
    assert "bola" in mulut.periksa_teks("Coba juga kata bola.", 20, {"mu"})
    # Di laporan, kata sehari-hari seperti "ibu" tidak ditolak.
    assert mulut.periksa_teks("Ibu bisa menemani sambil menatap mata anak.", 30) is None


# ------------------------------------------------------------ alasan tugas


def test_alasan_dari_llm_dipakai_kalau_lolos_dan_nama_diganti():
    usulan = usulan_contoh()
    kata = [u["item"]["teks"] for u in usulan]
    jawaban = {"tugas": [{"kata": k, "alasan": "ANAK perlu mengulang bunyi ini."} for k in kata]}
    hasil = asyncio.run(mulut.alasan_tugas(usulan, "Raka", llm_palsu(jawaban)))
    assert hasil["sumber"] == "llm"
    assert all(t["alasan"] == "Raka perlu mengulang bunyi ini." for t in hasil["tugas"])
    assert [t["item"]["teks"] for t in hasil["tugas"]] == kata


@pytest.mark.parametrize(
    "rusak",
    [
        None,  # LLM gagal atau tidak diatur
        {"tugas": "bukan daftar"},
        {"tugas": [{"kata": "bola", "alasan": "Kata lain."}] * 3},  # kata di luar usulan Otak
        {"salah_kunci": []},
    ],
)
def test_alasan_jatuh_ke_templat_kalau_keluaran_tidak_lolos(rusak):
    usulan = usulan_contoh()
    hasil = asyncio.run(mulut.alasan_tugas(usulan, "Raka", llm_palsu(rusak)))
    assert hasil["sumber"] == "templat"
    assert len(hasil["tugas"]) == 3 and all(t["alasan"] for t in hasil["tugas"])


def test_alasan_dengan_angka_ditolak():
    usulan = usulan_contoh()
    kata = [u["item"]["teks"] for u in usulan]
    jawaban = {"tugas": [{"kata": k, "alasan": "Penguasaan baru 40 persen."} for k in kata]}
    hasil = asyncio.run(mulut.alasan_tugas(usulan, "Raka", llm_palsu(jawaban)))
    assert hasil["sumber"] == "templat"


# ------------------------------------------------- ringkasan dan laporan


def test_ringkasan_kelas_templat_dan_llm():
    anak = [
        {"nama": "Raka", "macet": ["u"], "naik": []},
        {"nama": "Sinta", "macet": [], "naik": ["a", "M"]},
    ]
    templat = asyncio.run(mulut.ringkasan_kelas(anak, llm_palsu(None)))
    assert templat["sumber"] == "templat"
    assert "Raka (bunyi u)" in templat["ringkasan"] and "Sinta (bunyi a dan m/b/p)" in templat["ringkasan"]

    bagus = {"ringkasan": "ANAK_1 masih kesulitan di bunyi u. ANAK_2 membaik di bunyi a."}
    dari_llm = asyncio.run(mulut.ringkasan_kelas(anak, llm_palsu(bagus)))
    assert dari_llm == {
        "ringkasan": "Raka masih kesulitan di bunyi u. Sinta membaik di bunyi a.",
        "sumber": "llm",
    }

    ngarang = {"ringkasan": "ANAK_7 perlu perhatian."}  # penanda yang tidak ada di kelas
    assert asyncio.run(mulut.ringkasan_kelas(anak, llm_palsu(ngarang)))["sumber"] == "templat"


def test_laporan_mingguan_templat_dan_llm():
    data = {
        "sudah_bisa": [{"bunyi": "a", "tingkat": 2}, {"bunyi": "i", "tingkat": 2}],
        "sedang_dilatih": [{"bunyi": "a", "tingkat": 3}, {"bunyi": "u", "tingkat": 2}],
        "hari_latihan": 4, "tips": "Latihan di depan cermin.",
    }
    templat = asyncio.run(mulut.laporan_mingguan(data, "Raka", llm_palsu(None)))
    assert templat["sumber"] == "templat"
    assert templat["sudah_bisa"] == "Raka sudah bisa bunyi a dan i di tahap bunyi tunggal."
    assert templat["sedang_dilatih"] == (
        "Saat ini Raka berlatih bunyi a di tahap suku kata; bunyi u di tahap bunyi tunggal."
    )
    assert templat["cara_membantu"] == "Latihan di depan cermin."

    bagus = {
        "sudah_bisa": "ANAK sudah lancar bunyi a.",
        "sedang_dilatih": "ANAK masih berlatih bunyi i dan u.",
        "cara_membantu": "Ibu bisa menemani ANAK berlatih di depan cermin.",
    }
    dari_llm = asyncio.run(mulut.laporan_mingguan(data, "Raka", llm_palsu(bagus)))
    assert dari_llm["sumber"] == "llm" and dari_llm["cara_membantu"].startswith("Ibu bisa menemani Raka")

    kurang = {"sudah_bisa": "ANAK sudah lancar.", "sedang_dilatih": "Bunyi i."}  # satu bagian hilang
    assert asyncio.run(mulut.laporan_mingguan(data, "Raka", llm_palsu(kurang)))["sumber"] == "templat"


def test_llm_tanpa_pengaturan_mengembalikan_none(monkeypatch):
    for kunci in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(kunci, raising=False)
    assert not llm.tersedia()
    assert asyncio.run(llm.panggil_json("sistem", "pesan")) is None


# ------------------------------------------------------------------------ API


@pytest.fixture
def klien(monkeypatch):
    for kunci in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(kunci, raising=False)
    app = FastAPI()
    app.include_router(buat_router(demo=True))
    return TestClient(app)


def test_alur_sesi_sampai_naik_tingkat(klien):
    berikut = klien.post("/ai/anak/raka/sesi").json()["berikutnya"]
    assert berikut["item"] == {
        "id": "t1-a", "tingkat": 1, "teks": "a", "urutan": ["a"], "bantuan_visual": True,
    }
    urutan_id = []
    for _ in range(6):
        urutan_id.append(berikut["item"]["id"])
        jawab = klien.post(
            "/ai/anak/raka/percobaan",
            json={"item_id": berikut["item"]["id"], "berhasil": True, "langkah_tercapai": 1},
        ).json()
        berikut = jawab["berikutnya"]
    # "a" tiga kali (batas ulang berturut-turut), selingan "i", "a" sekali lagi sampai tuntas,
    # lalu lima berhasil beruntun menaikkan tingkat.
    assert urutan_id == ["t1-a", "t1-a", "t1-a", "t1-i", "t1-a", "t2-a"]
    assert jawab["tingkat_berhasil"] == 1.0

    peta = klien.get("/ai/anak/raka/peta").json()
    a = next(b for b in peta["bunyi"] if b["bunyi"] == "a")
    assert (a["tingkat"], a["label"], a["warna"]) == (2, "sedang_dilatih", "merah")
    assert a["tingkat_tuntas"] == 1
    assert peta["hari_latihan_minggu_ini"] == 1 and peta["sintetis"] is False


def test_tiga_gagal_memunculkan_istirahat(klien):
    klien.post("/ai/demo/isi", json={"anak_id": "sinta", "profil": "menengah"})
    klien.post("/ai/anak/sinta/sesi")
    for _ in range(3):
        jawab = klien.post(
            "/ai/anak/sinta/percobaan", json={"item_id": "t2-u", "berhasil": False}
        ).json()
    assert jawab["berikutnya"]["istirahat"] is True
    assert jawab["berikutnya"]["item"]["id"] == "t1-u"


def test_item_tidak_dikenal_ditolak(klien):
    jawab = klien.post("/ai/anak/raka/percobaan", json={"item_id": "t9-x", "berhasil": True})
    assert jawab.status_code == 404


def test_tugas_laporan_dan_ringkasan_tanpa_llm_memakai_templat(klien):
    klien.post("/ai/demo/isi", json={"anak_id": "sinta", "profil": "menengah"})

    tugas = klien.post("/ai/anak/sinta/tugas-usulan", json={"nama": "Sinta"}).json()
    assert tugas["sumber"] == "templat" and len(tugas["tugas"]) == 3
    assert tugas["tugas"][0]["bunyi_fokus"] == "u"
    assert all(t["alasan"] and t["teks_label"] for t in tugas["tugas"])

    laporan = klien.post("/ai/anak/sinta/laporan-mingguan", json={"nama": "Sinta"}).json()
    assert laporan["sumber"] == "templat"
    assert laporan["sudah_bisa"] == (
        "Sinta sudah bisa bunyi a di tahap bunyi tunggal; "
        "bunyi i, u, o dan m/b/p di tahap bunyi tunggal dengan bantuan gambar."
    )
    assert laporan["sedang_dilatih"] == "Saat ini Sinta berlatih bunyi i dan u di tahap bunyi tunggal."

    ringkasan = klien.post(
        "/ai/kelas/ringkasan",
        json={"anak": [{"anak_id": "sinta", "nama": "Sinta"}, {"anak_id": "baru", "nama": "Bimo"}]},
    ).json()
    assert ringkasan == {
        "ringkasan": "Yang perlu perhatian: Sinta (bunyi u). Yang membaik minggu ini: Sinta (bunyi a).",
        "sumber": "templat",
    }

    assert klien.get("/ai/anak/sinta/peta").json()["sintetis"] is True


def test_kurikulum_dan_status(klien):
    kurikulum = klien.get("/ai/kurikulum").json()
    assert kurikulum["bunyi"] == ["a", "i", "u", "o", "M"] and len(kurikulum["item"]) == 46
    assert klien.get("/ai/status").json() == {
        "llm_tersedia": False,
        "llm_kurang": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"],
        "berkas_env": "tidak dimuat",
        "mode_demo": True,
    }


def test_endpoint_demo_tidak_ada_di_luar_mode_demo(monkeypatch):
    app = FastAPI()
    app.include_router(buat_router(demo=False))
    assert TestClient(app).post("/ai/demo/isi", json={"anak_id": "x"}).status_code == 404


# ------------------------------------------------------------ klien LLM (HTTP)


def pasang_llm_tiruan(monkeypatch, penangan):
    import httpx

    monkeypatch.setenv("LLM_BASE_URL", "https://llm.contoh/v1/")
    monkeypatch.setenv("LLM_API_KEY", "kunci-uji")
    monkeypatch.setenv("LLM_MODEL", "model-uji")
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    monkeypatch.setattr(llm, "_pakai_format_json", True)
    asli = httpx.AsyncClient
    monkeypatch.setattr(
        llm.httpx, "AsyncClient", lambda **kw: asli(transport=httpx.MockTransport(penangan), **kw)
    )


def test_klien_llm_mengirim_permintaan_yang_benar_dan_membaca_json(monkeypatch):
    import httpx, json

    terkirim = {}

    def penangan(permintaan: httpx.Request) -> httpx.Response:
        terkirim["url"] = str(permintaan.url)
        terkirim["auth"] = permintaan.headers["authorization"]
        terkirim["badan"] = json.loads(permintaan.content)
        isi = json.dumps({"ringkasan": "Baik."})
        return httpx.Response(200, json={"choices": [{"message": {"content": isi}}]})

    pasang_llm_tiruan(monkeypatch, penangan)
    assert asyncio.run(llm.panggil_json("aturan", "data")) == {"ringkasan": "Baik."}
    assert terkirim["url"] == "https://llm.contoh/v1/chat/completions"
    assert terkirim["auth"] == "Bearer kunci-uji"
    assert terkirim["badan"]["model"] == "model-uji"
    assert terkirim["badan"]["response_format"] == {"type": "json_object"}
    assert terkirim["badan"]["max_tokens"] == 2000  # cukup longgar untuk model yang berpikir dulu
    assert "reasoning_effort" not in terkirim["badan"]
    assert [m["role"] for m in terkirim["badan"]["messages"]] == ["system", "user"]


@pytest.mark.parametrize(
    "jawaban",
    [
        lambda: __import__("httpx").Response(429, json={"error": "kuota habis"}),
        lambda: __import__("httpx").Response(200, json={"choices": [{"message": {"content": "bukan json"}}]}),
        lambda: __import__("httpx").Response(200, json={"choices": [{"message": {"content": "[1, 2]"}}]}),
        lambda: __import__("httpx").Response(200, json={"aneh": True}),
    ],
)
def test_klien_llm_gagal_dengan_tenang(monkeypatch, jawaban):
    pasang_llm_tiruan(monkeypatch, lambda permintaan: jawaban())
    assert asyncio.run(llm.panggil_json("aturan", "data")) is None


def test_klien_llm_timeout_jatuh_ke_templat(monkeypatch):
    import httpx

    def penangan(permintaan):
        raise httpx.ReadTimeout("lama", request=permintaan)

    pasang_llm_tiruan(monkeypatch, penangan)
    hasil = asyncio.run(mulut.ringkasan_kelas([{"nama": "Raka", "macet": ["u"], "naik": []}]))
    assert hasil["sumber"] == "templat" and "Raka (bunyi u)" in hasil["ringkasan"]


def test_klien_llm_meneruskan_reasoning_effort_dan_batas_token(monkeypatch):
    import httpx, json

    terkirim = {}

    def penangan(permintaan):
        terkirim.update(json.loads(permintaan.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    pasang_llm_tiruan(monkeypatch, penangan)
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    monkeypatch.setenv("LLM_MAKS_TOKEN", "3000")
    assert asyncio.run(llm.panggil_json("aturan", "data")) == {}
    assert terkirim["reasoning_effort"] == "low" and terkirim["max_tokens"] == 3000


def test_klien_llm_mencoba_lagi_tanpa_response_format_kalau_ditolak(monkeypatch):
    import httpx, json

    badan_masuk = []

    def penangan(permintaan):
        badan = json.loads(permintaan.content)
        badan_masuk.append(badan)
        if "response_format" in badan:
            return httpx.Response(400, json={"error": {"message": "response_format tidak didukung"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ringkasan": "Baik."}'}}]})

    pasang_llm_tiruan(monkeypatch, penangan)
    assert asyncio.run(llm.panggil_json("aturan", "data")) == {"ringkasan": "Baik."}
    assert ["response_format" in b for b in badan_masuk] == [True, False]
    # Panggilan berikutnya langsung tanpa response_format, tidak membuang satu permintaan lagi.
    assert asyncio.run(llm.panggil_json("aturan", "data")) == {"ringkasan": "Baik."}
    assert ["response_format" in b for b in badan_masuk] == [True, False, False]


@pytest.mark.parametrize(
    "isi",
    [
        '{"ringkasan": "Baik."}',
        '```json\n{"ringkasan": "Baik."}\n```',
        'Berikut jawabannya:\n{"ringkasan": "Baik."}',
    ],
)
def test_json_terbaca_walau_dibungkus(isi):
    assert llm.urai_json(isi) == {"ringkasan": "Baik."}


@pytest.mark.parametrize("isi", ["", "bukan json", "[1, 2]", "{rusak"])
def test_bukan_objek_json_ditolak(isi):
    assert llm.urai_json(isi) is None


def test_keluaran_terpotong_jatuh_ke_templat(monkeypatch):
    import httpx

    def penangan(permintaan):
        # Model kehabisan token saat berpikir: isi kosong, finish_reason "length".
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": None}}]}
        )

    pasang_llm_tiruan(monkeypatch, penangan)
    hasil = asyncio.run(mulut.ringkasan_kelas([{"nama": "Raka", "macet": ["u"], "naik": []}]))
    assert hasil["sumber"] == "templat"


# ------------------------------------------------------------- berkas .env


def test_urai_env_melewati_komentar_dan_membuang_kutip():
    from satu_ai.pengaturan import urai

    teks = "# komentar\n\nLLM_MODEL = gemini-x \nLLM_API_KEY='abc=123'\nexport SATU_DEMO=1\nbaris tanpa sama dengan\nKOSONG=\n"
    assert urai(teks) == {"LLM_MODEL": "gemini-x", "LLM_API_KEY": "abc=123", "SATU_DEMO": "1", "KOSONG": ""}


@pytest.mark.parametrize("pengodean", ["utf-8", "utf-8-sig", "utf-16"])
def test_env_terbaca_apa_pun_cara_notepad_menyimpannya(tmp_path, monkeypatch, pengodean):
    from satu_ai import pengaturan

    for nama in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "SATU_DEMO"):
        monkeypatch.delenv(nama, raising=False)
    isi = "LLM_BASE_URL=https://contoh/v1\r\nLLM_API_KEY=abc\r\nLLM_MODEL=model-x\r\nSATU_DEMO=1\r\n"
    (tmp_path / ".env").write_text(isi, encoding=pengodean, newline="")
    monkeypatch.setitem(pengaturan.STATUS, "berkas_env", "tidak dimuat")
    assert pengaturan.muat_env(tmp_path) == "terbaca, 4 baris pengaturan"
    assert llm.tersedia() and llm.kurang() == []
    import os

    assert os.environ["SATU_DEMO"] == "1"
    for nama in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "SATU_DEMO"):
        monkeypatch.delenv(nama, raising=False)  # jangan bocor ke tes lain


def test_env_tidak_menimpa_variabel_yang_sudah_ada_dan_melaporkan_berkas_hilang(tmp_path, monkeypatch):
    from satu_ai import pengaturan

    monkeypatch.setitem(pengaturan.STATUS, "berkas_env", "tidak dimuat")
    assert "salin .env.example jadi .env" in pengaturan.muat_env(tmp_path)
    (tmp_path / ".env.txt").write_text("LLM_MODEL=x\n")
    assert pengaturan.muat_env(tmp_path) == "tidak ada, tapi ada .env.txt: ganti namanya jadi .env"

    # Berkas dibuat di folder utama repo, bukan di backend.
    backend = tmp_path / "backend"
    backend.mkdir()
    (tmp_path / ".env").write_text("LLM_MODEL=dari-berkas\n")
    assert pengaturan.muat_env(backend).startswith("salah tempat: ada di ")

    monkeypatch.setenv("LLM_MODEL", "dari-lingkungan")
    pengaturan.muat_env(tmp_path)
    import os

    assert os.environ["LLM_MODEL"] == "dari-lingkungan"


def test_kunci_yang_masih_teks_contoh_dianggap_belum_diisi(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://contoh/v1")
    monkeypatch.setenv("LLM_MODEL", "model-x")
    monkeypatch.setenv("LLM_API_KEY", "tempel-kunci-kamu-di-sini")
    assert not llm.tersedia()
    assert llm.kurang() == ["LLM_API_KEY (masih teks contoh, ganti dengan kunci asli)"]
    monkeypatch.delenv("LLM_API_KEY")
    assert llm.kurang() == ["LLM_API_KEY"]
