"""Pemanggil LLM satu pintu, lewat endpoint yang kompatibel dengan OpenAI.

Diatur dari environment variable, supaya kunci API hanya ada di server:
  LLM_BASE_URL          Gemini: https://generativelanguage.googleapis.com/v1beta/openai
                        Groq:   https://api.groq.com/openai/v1
  LLM_API_KEY           kunci API
  LLM_MODEL             nama model di penyedia itu
  LLM_BATAS_DETIK       batas waktu satu panggilan, bawaan 12
  LLM_MAKS_TOKEN        batas token keluaran, bawaan 2000. Model yang "berpikir" dulu
                        (Gemini 3 dan sejenisnya) memakai sebagian batas ini untuk berpikir,
                        jadi jangan dibuat kecil.
  LLM_REASONING_EFFORT  opsional: minimal, low, medium, atau high. Kosong = bawaan penyedia.

Kalau tiga yang pertama ada yang kosong, atau panggilan gagal, fungsi mengembalikan
None dan pemanggil memakai templat.
"""

import json
import logging
import os

import httpx

log = logging.getLogger("satu_ai.llm")

# Tidak semua penyedia menerima response_format json_object. Kalau ditolak sekali,
# panggilan berikutnya langsung tanpa itu; JSON tetap diminta lewat instruksi.
_pakai_format_json = True


_WAJIB = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
# Teks contoh dari .env.example dan panduan; kalau masih ini, kuncinya belum diisi.
_KUNCI_CONTOH = {"tempel-kunci-kamu-di-sini", "kunci-kamu", "kunci-dari-ai-studio"}


def kurang() -> list[str]:
    """Nama pengaturan LLM yang belum diisi. Kosong berarti siap dipakai."""
    hasil = [nama for nama in _WAJIB if not os.getenv(nama)]
    if os.getenv("LLM_API_KEY") in _KUNCI_CONTOH:
        hasil.append("LLM_API_KEY (masih teks contoh, ganti dengan kunci asli)")
    return hasil


def tersedia() -> bool:
    return not kurang()


def urai_json(isi: str) -> dict | None:
    """Membaca objek JSON dari jawaban, juga kalau dibungkus pagar kode atau diberi kata pengantar."""
    teks = isi.strip()
    calon = [teks]
    awal, akhir = teks.find("{"), teks.rfind("}")
    if 0 <= awal < akhir:
        calon.append(teks[awal : akhir + 1])
    for c in calon:
        try:
            hasil = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(hasil, dict):
            return hasil
    return None


async def panggil_json(sistem: str, pesan: str) -> dict | None:
    """Meminta jawaban JSON. Mengembalikan dict, atau None kalau gagal apa pun sebabnya."""
    global _pakai_format_json
    if not tersedia():
        return None
    url = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    badan: dict = {
        "model": os.environ["LLM_MODEL"],
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user", "content": pesan},
        ],
        "max_tokens": int(os.getenv("LLM_MAKS_TOKEN", "2000")),
    }
    if os.getenv("LLM_REASONING_EFFORT"):
        badan["reasoning_effort"] = os.environ["LLM_REASONING_EFFORT"]
    kepala = {"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"}
    batas = float(os.getenv("LLM_BATAS_DETIK", "12"))

    try:
        async with httpx.AsyncClient(timeout=batas) as klien:
            if _pakai_format_json:
                jawab = await klien.post(
                    url, json={**badan, "response_format": {"type": "json_object"}}, headers=kepala
                )
                if jawab.status_code == 400:
                    log.warning("Penyedia menolak response_format; dicoba tanpa itu")
                    _pakai_format_json = False
            if not _pakai_format_json:
                jawab = await klien.post(url, json=badan, headers=kepala)

        if jawab.status_code != 200:
            log.warning("LLM menjawab HTTP %s: %s", jawab.status_code, jawab.text[:300])
            return None
        pilihan = jawab.json()["choices"][0]
        isi = pilihan["message"].get("content") or ""
        hasil = urai_json(isi)
        if hasil is None:
            # finish_reason "length" berarti keluaran terpotong: naikkan LLM_MAKS_TOKEN.
            log.warning(
                "Jawaban LLM bukan JSON (finish_reason=%s): %r",
                pilihan.get("finish_reason"),
                isi[:200],
            )
        return hasil
    except Exception as galat:  # jaringan, timeout, bentuk jawaban tak terduga: jatuh ke templat
        log.warning("LLM gagal, pakai templat: %s: %s", type(galat).__name__, galat)
        return None
