import random
from datetime import datetime, timedelta, timezone

import pytest

from satu_ai import bkt, otak
from satu_ai.kurikulum import BUNYI, ITEM, ITEM_PER_ID, PARAM, PARUH_LUPA_HARI, urutan_dari_teks

T0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


def catat(status, item_id, berhasil, langkah=None, waktu=T0):
    item = ITEM_PER_ID[item_id]
    if langkah is None:
        langkah = len(item.urutan) if berhasil else 0
    return otak.catat_percobaan(status, item, berhasil, langkah, waktu)


# ----------------------------------------------------------------------- BKT


def test_bkt_berhasil_menaikkan_sesuai_rumus():
    # 0,30 -> pasca 0,27/0,515 = 0,5243 -> ditambah peluang belajar 0,05 dari sisanya
    assert bkt.perbarui(0.30, True, PARAM[1]) == pytest.approx(0.5481, abs=1e-4)


def test_bkt_gagal_menurunkan():
    assert bkt.perbarui(0.70, False, PARAM[1]) < 0.70


def test_bkt_perkiraan_berhasil():
    assert bkt.perkiraan_berhasil(0.30, PARAM[1]) == pytest.approx(0.515)


def test_luruh_setengah_selisih_setelah_satu_paruh():
    assert bkt.luruh(0.90, 0.30, 7, 7) == pytest.approx(0.60)
    assert bkt.luruh(0.90, 0.30, 0, 7) == 0.90
    assert bkt.luruh(0.20, 0.30, 30, 7) == 0.20  # tidak naik ke nilai awal


# ----------------------------------------------------------------- kurikulum


@pytest.mark.parametrize(
    "teks, urutan",
    [
        ("bola", ("M", "o", "T", "a")),
        ("mama", ("M", "a", "M", "a")),
        ("buku", ("M", "u", "T", "u")),
        ("ibu", ("i", "M", "u")),
        ("susu", ("S", "u", "S", "u")),
        ("anggur", ("a", "T", "u", "T")),  # "ngg" digabung jadi satu bunyi lidah
        ("mobil", ("M", "o", "M", "i", "T")),
        # Bentuk baru: e, f/v, h, dan w/y yang dinilai sebagai u/i.
        ("meja", ("M", "e", "S", "a")),
        ("maaf", ("M", "a", "F")),
        ("wahyu", ("u", "a", "H", "i", "u")),
        ("ayah", ("a", "i", "a", "H")),
        ("hiu", ("H", "i", "u")),
        ("ayo", ("a", "i", "o")),
    ],
)
def test_urutan_bentuk(teks, urutan):
    assert urutan_dari_teks(teks) == urutan


def test_semua_item_punya_urutan_dan_id_unik():
    assert all(it.urutan for it in ITEM)
    assert len({it.id for it in ITEM}) == len(ITEM)


# ------------------------------------------------------------------ mencatat


def test_tiga_berhasil_jadi_sudah_bisa_dan_tidak_dilatih_lagi_sementara():
    s = otak.StatusAnak()
    for _ in range(2):
        catat(s, "t1-a", True)
    assert "t1-a" in [it.id for it in otak._kandidat(s, T0)]
    catat(s, "t1-a", True)
    assert 0.85 <= otak.p_kini(s, "a", 1, T0) < 0.95
    assert "t1-a" not in [it.id for it in otak._kandidat(s, T0)]


def test_tingkat_dua_terbuka_setelah_prasyarat():
    s = otak.StatusAnak()
    catat(s, "t1-a", True)
    assert not otak.prasyarat_terpenuhi(s, ITEM_PER_ID["t2-a"], T0)  # satu berhasil belum cukup
    catat(s, "t1-a", True)
    assert otak.prasyarat_terpenuhi(s, ITEM_PER_ID["t2-a"], T0)
    assert not otak.prasyarat_terpenuhi(s, ITEM_PER_ID["t2-i"], T0)


def test_kemunduran_di_tingkat_bawah_tidak_mengunci_tingkat_yang_sudah_berjalan():
    s = otak.StatusAnak()
    s.kc[("u", 2)] = otak.KC(p=0.40, n=6, terakhir=T0)  # mundur di tingkat 2
    s.kc[("M", 2)] = otak.KC(p=0.97, n=4, terakhir=T0, tuntas=True)
    s.kc[("u", 3)] = otak.KC(p=0.80, n=4, terakhir=T0)  # tapi sudah berjalan di tingkat 3
    s.kc[("M", 3)] = otak.KC(p=0.80, n=4, terakhir=T0)
    assert otak.prasyarat_terpenuhi(s, ITEM_PER_ID["t3-mu"], T0)
    pilihan = otak.pilih_berikutnya(s, T0)
    assert otak.prasyarat_terpenuhi(s, pilihan.item, T0)


def test_kata_gagal_hanya_mengubah_bunyi_yang_lewat_dan_yang_macet():
    s = otak.StatusAnak()
    perubahan = catat(s, "t4-bola", False, langkah=1)  # M lewat, macet di o, a belum sampai
    hasil = {p["bunyi"]: p["berhasil"] for p in perubahan}
    assert hasil == {"M": True, "o": False}
    assert ("a", 4) not in s.kc


def test_bunyi_yang_macet_tidak_dihitung_berhasil_walau_pernah_lewat():
    s = otak.StatusAnak()
    perubahan = catat(s, "t4-mama", False, langkah=2)  # M, a lewat, macet di M kedua
    assert {p["bunyi"]: p["berhasil"] for p in perubahan} == {"a": True, "M": False}


def test_langkah_di_luar_rentang_tidak_membuat_galat():
    s = otak.StatusAnak()
    perubahan = catat(s, "t4-bola", False, langkah=99)
    assert perubahan[-1] == {**perubahan[-1], "bunyi": "a", "berhasil": False}


def test_sesi_baru_setelah_jeda_panjang():
    s = otak.StatusAnak()
    for _ in range(6):
        catat(s, "t1-a", True)
    assert len(s.jendela) == 6
    catat(s, "t1-i", True, waktu=T0 + timedelta(hours=2))
    assert s.jendela == [True]


def test_tingkat_berhasil_butuh_minimal_lima_percobaan():
    s = otak.StatusAnak()
    for _ in range(4):
        catat(s, "t1-a", True)
    assert otak.tingkat_berhasil(s) is None
    catat(s, "t1-a", False)
    assert otak.tingkat_berhasil(s) == pytest.approx(0.8)


def test_simpan_dan_muat_kembali_sama():
    s = otak.StatusAnak()
    catat(s, "t1-a", True)
    catat(s, "t4-bola", False, langkah=1)
    assert otak.StatusAnak.dari_dict(s.ke_dict()).ke_dict() == s.ke_dict()


# ------------------------------------------------------------------- memilih


def test_anak_baru_mulai_dari_bunyi_pertama_tingkat_satu():
    pilihan = otak.pilih_berikutnya(otak.StatusAnak(), T0)
    assert pilihan.item.id == "t1-a" and not pilihan.istirahat


def test_tiga_gagal_beruntun_turun_tingkat_dan_istirahat():
    s = otak.StatusAnak()
    for b in ("a", "u"):
        for _ in range(3):
            catat(s, f"t1-{b}", True)
    for _ in range(3):
        catat(s, "t2-u", False)
    pilihan = otak.pilih_berikutnya(s, T0)
    assert (pilihan.item.id, pilihan.alasan, pilihan.istirahat) == ("t1-u", "turun_tingkat", True)
    # Memanggil lagi tanpa percobaan baru memberi jawaban yang sama.
    assert otak.pilih_berikutnya(s, T0).item.id == "t1-u"
    catat(s, "t1-u", True)
    assert not otak.pilih_berikutnya(s, T0).istirahat


def test_gagal_di_kata_turun_ke_suku_kata_dengan_bunyi_yang_macet():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t4-buku", False, langkah=1)  # macet di u
    pilihan = otak.pilih_berikutnya(s, T0)
    assert pilihan.item.tingkat == 3 and "u" in pilihan.item.bunyi and pilihan.istirahat


def test_tiga_gagal_di_tingkat_satu_ganti_bunyi():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t1-a", False)
    pilihan = otak.pilih_berikutnya(s, T0)
    assert pilihan.alasan == "ganti_bunyi" and pilihan.istirahat
    assert "a" not in pilihan.item.bunyi


def test_tingkat_berhasil_rendah_memberi_latihan_penguatan_yang_sudah_tuntas():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t1-a", True)
    # Jendela dibuat rendah tanpa memicu aturan tiga gagal beruntun.
    s.jendela = [True, False, False, True, False, False]
    s.gagal_beruntun, s.turun = 0, None
    pilihan = otak.pilih_berikutnya(s, T0)
    assert (pilihan.item.id, pilihan.alasan) == ("t1-a", "penguatan")
    assert pilihan.perkiraan >= 0.70


def test_tingkat_berhasil_rendah_tanpa_latihan_mudah_menyingkirkan_tingkat_tertinggi():
    s = otak.StatusAnak()
    # Tingkat 2 terbuka, tapi belum ada item yang perkiraan berhasilnya 70% ke atas.
    s.kc[("a", 1)] = otak.KC(p=0.62, n=2, terakhir=T0)
    s.jendela = [True, False, False, True, False, False]
    pilihan = otak.pilih_berikutnya(s, T0)
    assert pilihan.alasan == "lebih_mudah" and pilihan.item.tingkat == 1


def test_tingkat_berhasil_tinggi_menaikkan_tingkat():
    s = otak.StatusAnak()
    for _ in range(5):
        catat(s, "t1-a", True)
    pilihan = otak.pilih_berikutnya(s, T0)
    assert (pilihan.item.id, pilihan.alasan) == ("t2-a", "lebih_sulit")


def test_tidak_mengulang_item_yang_sama_lebih_dari_tiga_kali():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t1-a", False)
        s.gagal_beruntun, s.turun = 0, None
    assert otak.pilih_berikutnya(s, T0).item.id != "t1-a"


def test_tidak_kembali_ke_tingkat_bawah_setelah_naik():
    s = otak.StatusAnak()
    catat(s, "t1-i", True)
    catat(s, "t1-i", True)  # 0,93: belum tuntas di tingkat 1
    for _ in range(3):
        catat(s, "t2-i", True)
    assert "t1-i" not in [it.id for it in otak._kandidat(s, T0)]


def test_tanpa_kandidat_tidak_melompat_ke_tingkat_yang_belum_terbuka():
    s = otak.StatusAnak()
    for b in BUNYI:
        s.kc[(b, 1)] = otak.KC(p=0.99, n=5, terakhir=T0, tuntas=True)
        s.kc[(b, 2)] = otak.KC(p=0.99, n=5, terakhir=T0, tuntas=True)
    for it in ITEM:
        if it.tingkat == 3:
            for b in it.bunyi:
                s.kc[(b, 3)] = otak.KC(p=0.99, n=5, terakhir=T0, tuntas=True)
    # Tingkat 4 terbuka dan belum tuntas, jadi masih ada kandidat biasa.
    assert otak.pilih_berikutnya(s, T0).item.tingkat == 4


def test_semua_tuntas_tetap_memberi_latihan():
    s = otak.StatusAnak()
    for it in ITEM:
        for b in it.bunyi:
            s.kc[(b, it.tingkat)] = otak.KC(p=0.99, n=5, terakhir=T0)
    pilihan = otak.pilih_berikutnya(s, T0)
    assert pilihan.alasan == "ulang_tuntas" and pilihan.item.tingkat == 4


def test_pemilihan_acak_selalu_memberi_kandidat_yang_sah():
    rng = random.Random(7)
    s = otak.StatusAnak()
    waktu = T0
    for _ in range(300):
        pilihan = otak.pilih_berikutnya(s, waktu, rng)
        assert otak.prasyarat_terpenuhi(s, pilihan.item, waktu) or pilihan.alasan == "turun_tingkat"
        berhasil = rng.random() < 0.75
        otak.catat_percobaan(s, pilihan.item, berhasil, rng.randrange(len(pilihan.item.urutan)), waktu)
        waktu += timedelta(seconds=20)
    assert otak.tingkat_tercapai(s) >= 3  # anak yang cukup sering berhasil sampai ke suku kata


# -------------------------------------------------------- lupa, peta, tugas


def test_penguasaan_turun_kalau_lama_tidak_dilatih():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t1-a", True)
    sekarang = otak.p_kini(s, "a", 1, T0)
    nanti = otak.p_kini(s, "a", 1, T0 + timedelta(days=PARUH_LUPA_HARI))
    assert nanti == pytest.approx(0.30 + (sekarang - 0.30) / 2)


def test_yang_pernah_tuntas_baru_diulang_setelah_turun_jauh():
    s = otak.StatusAnak()
    for _ in range(4):
        catat(s, "t1-a", True)
    kandidat = lambda hari: [it.id for it in otak._kandidat(s, T0 + timedelta(days=hari))]
    assert "t1-a" not in kandidat(3)  # sedikit lupa: belum diulang
    assert "t1-a" in kandidat(20)  # sudah di bawah "sudah bisa": diulang


def test_peta_menandai_bunyi_yang_belum_dilatih():
    s = otak.StatusAnak()
    catat(s, "t1-a", True)
    baris = {b["bunyi"]: b for b in otak.peta(s, T0)}
    assert baris["a"]["tingkat"] == 1 and baris["a"]["label"] == "hampir_bisa"
    assert baris["a"]["tingkat_tuntas"] == 0
    assert baris["i"]["tingkat"] == 0 and baris["i"]["label"] == "belum_dilatih"


def test_insight_macet_dan_naik():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t1-a", True)
    for _ in range(6):
        catat(s, "t1-u", False)
    temuan = otak.insight(s, T0)
    assert temuan["naik"] == [{"bunyi": "a", "tingkat": 1}]
    assert temuan["macet"] == [{"bunyi": "u", "tingkat": 1, "percobaan": 6}]


def test_tugas_anak_baru_tiga_bunyi_tingkat_satu():
    usulan = otak.usul_tugas(otak.StatusAnak(), T0)
    assert [u["item"]["id"] for u in usulan] == ["t1-a", "t1-i", "t1-u"]
    assert all(u["label"] == "belum_dilatih" for u in usulan)


def test_tugas_mendahulukan_yang_pernah_dilatih_daripada_materi_baru():
    s = otak.StatusAnak()
    catat(s, "t1-a", True)
    usulan = otak.usul_tugas(s, T0)
    assert [u["item"]["id"] for u in usulan] == ["t1-a", "t1-i", "t1-u"]
    assert [u["label"] for u in usulan] == ["hampir_bisa", "belum_dilatih", "belum_dilatih"]


def test_tugas_mengutamakan_bunyi_yang_mulai_lupa_dan_tidak_melampaui_tingkat_anak():
    s = otak.StatusAnak()
    lama = T0 - timedelta(days=10)
    for b in ("a", "i", "u", "o", "M"):
        for _ in range(3):
            catat(s, f"t1-{b}", True, waktu=T0 if b != "o" else lama)
    usulan = otak.usul_tugas(s, T0)
    assert usulan[0]["bunyi_fokus"] == "o" and usulan[0]["hari_sejak_latihan"] == 10
    assert all(u["item"]["tingkat"] <= 1 for u in usulan)
    assert len({u["item"]["id"] for u in usulan}) == 3


def test_hari_latihan_minggu_ini():
    s = otak.StatusAnak()
    for hari in (0, 1, 3, 9):
        catat(s, "t1-a", True, waktu=T0 - timedelta(days=hari))
    assert otak.hari_latihan_minggu_ini(s, T0) == 3


def test_streak_hari_berturut_turut_menurut_wib():
    s = otak.StatusAnak()
    for hari in (0, 1, 2, 4):
        catat(s, "t1-a", True, waktu=T0 - timedelta(days=hari))
    assert otak.streak(s, T0) == 3  # hari ini, kemarin, lusa; hari ke-4 terputus
    # Besok belum berlatih: streak masih 3. Lusa tanpa latihan: putus.
    assert otak.streak(s, T0 + timedelta(days=1)) == 3
    assert otak.streak(s, T0 + timedelta(days=2)) == 0
    assert otak.streak(otak.StatusAnak(), T0) == 0


def test_latihan_pagi_wib_tercatat_di_tanggal_wib():
    s = otak.StatusAnak()
    pagi_wib = datetime(2026, 11, 14, 23, 30, tzinfo=timezone.utc)  # 15 Nov 06.30 WIB
    catat(s, "t1-a", True, waktu=pagi_wib)
    assert s.hari_latihan == ["2026-11-15"]


def test_kata_dengan_h_baru_terbuka_setelah_h_dilatih_di_suku_kata():
    hiu = ITEM_PER_ID["t4-hiu"]
    s = otak.StatusAnak()
    for b in ("i", "u"):
        s.kc[(b, 3)] = otak.KC(p=0.9, n=5, terakhir=T0)
    assert not otak.prasyarat_terpenuhi(s, hiu, T0)  # h belum dilatih
    s.kc[("H", 3)] = otak.KC(p=0.9, n=5, terakhir=T0)
    assert otak.prasyarat_terpenuhi(s, hiu, T0)


# ------------------------------------------------------------ level dan riwayat


def test_anak_baru_hanya_level_1_terbuka_dan_latihan_tidak_melewati_level_terbuka():
    s = otak.StatusAnak()
    peta = otak.status_level(s, T0)
    assert peta["level_sekarang"] == 1
    assert [lv["status"] for lv in peta["level"]] == ["terbuka"] + ["terkunci"] * 5
    level_dipakai = []
    for _ in range(40):
        batas = otak.level_terbuka_tertinggi(s, T0)
        pilihan = otak.pilih_berikutnya(s, T0)
        assert pilihan.item.level <= batas
        level_dipakai.append(pilihan.item.level)
        otak.catat_percobaan(s, pilihan.item, True, len(pilihan.item.urutan), T0)
    assert level_dipakai[:5] == [1] * 5 and max(level_dipakai) > 1  # naik level setelah maju


def test_level_berikutnya_terbuka_setelah_40_persen_dan_tuntas_dapat_3_bintang():
    s = otak.StatusAnak()
    for b in ("a", "i"):
        s.kc[(b, 1)] = otak.KC(p=0.9, n=4, terakhir=T0)
    peta = {lv["level"]: lv for lv in otak.status_level(s, T0)["level"]}
    assert peta[1]["kemajuan"] == pytest.approx(1 / 3, abs=1e-3) and peta[2]["status"] == "terkunci"
    s.kc[("u", 1)] = otak.KC(p=0.9, n=4, terakhir=T0)
    peta = {lv["level"]: lv for lv in otak.status_level(s, T0)["level"]}
    assert peta[1]["kemajuan"] == pytest.approx(0.5) and peta[2]["status"] == "terbuka"
    for b in ("a", "i", "u"):
        s.kc[(b, 2)] = otak.KC(p=0.9, n=4, terakhir=T0)
    peta = {lv["level"]: lv for lv in otak.status_level(s, T0)["level"]}
    assert (peta[1]["status"], peta[1]["bintang"]) == ("tuntas", 3)
    assert peta[2]["status"] == "terbuka" and peta[3]["status"] == "terkunci"
    assert otak.AMBANG_BUKA_LEVEL == 0.4
    assert otak.status_level(s, T0)["level_sekarang"] == 2


def test_level_yang_pernah_dilatih_tetap_terbuka():
    s = otak.StatusAnak()
    catat(s, "t1-M", True)  # misalnya guru membuka latihan m lebih dulu
    peta = {lv["level"]: lv["status"] for lv in otak.status_level(s, T0)["level"]}
    assert peta[3] == "terbuka" and peta[2] == "terkunci"


def test_riwayat_harian_dan_kemajuan_per_bunyi():
    s = otak.StatusAnak()
    kemarin = T0 - timedelta(days=1)
    catat(s, "t1-a", True, waktu=kemarin)
    catat(s, "t1-a", False, waktu=kemarin)
    for _ in range(3):
        catat(s, "t1-a", True)
    catat(s, "t2-a", True)
    r = otak.riwayat(s)
    assert [(h["tanggal"], h["percobaan"], h["berhasil"]) for h in r["harian"]] == [
        ("2026-11-13", 2, 1), ("2026-11-14", 4, 4),
    ]
    garis = r["per_bunyi"]["a"]
    assert [g["tingkat"] for g in garis] == [1, 2]  # tingkat tertinggi hari itu
    assert garis[1]["kemajuan"] > garis[0]["kemajuan"]
    assert otak.StatusAnak.dari_dict(s.ke_dict()).riwayat == s.riwayat


def test_riwayat_hanya_menyimpan_60_hari_terakhir():
    s = otak.StatusAnak()
    for hari in range(70):
        catat(s, "t1-a", True, waktu=T0 - timedelta(days=hari))
    assert len(s.riwayat) == 60 and min(s.riwayat) == "2026-09-16"


def test_penguatan_diselingi_bukan_terus_menerus():
    s = otak.StatusAnak()
    for _ in range(3):
        catat(s, "t1-a", True)  # "a" sudah bisa: bahan penguatan
    s.jendela = [False, False, True, False, False, True]
    s.gagal_beruntun, s.turun = 0, None
    pertama = otak.pilih_berikutnya(s, T0)
    assert pertama.alasan == "penguatan" and pertama.item.id == "t1-a"
    otak.catat_percobaan(s, pertama.item, True, 1, T0)
    s.jendela = [False, False, True, False, False, True]  # masih sering gagal
    kedua = otak.pilih_berikutnya(s, T0)
    assert kedua.alasan != "penguatan" and kedua.item.id != "t1-a"
