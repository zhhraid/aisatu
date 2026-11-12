"""Pemanggil LLM satu pintu, lewat endpoint yang kompatibel dengan OpenAI.

Diatur dari environment variable, supaya kunci API hanya ada di server:
  LLM_BASE_URL  contoh Groq:   https://api.groq.com/openai/v1
                contoh Gemini: https://generativelanguage.googleapis.com/v1beta/openai
  LLM_API_KEY   kunci API
  LLM_MODEL     nama model di penyedia itu
  LLM_BATAS_DETIK  batas waktu, bawaan 8

Kalau salah satu kosong, atau panggilan gagal, fungsi mengembalikan None
dan pemanggil memakai templat.
"""

import json
import logging
import os

import httpx

log = logging.getLogger("satu_ai.llm")


def tersedia() -> bool:
    return all(os.getenv(k) for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))


async def panggil_json(sistem: str, pesan: str, maks_token: int = 400) -> dict | None:
    """Meminta jawaban JSON. Mengembalikan dict, atau None kalau gagal apa pun sebabnya."""
    if not tersedia():
        return None
    url = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    badan = {
        "model": os.environ["LLM_MODEL"],
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user", "content": pesan},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        "max_tokens": maks_token,
    }
    batas = float(os.getenv("LLM_BATAS_DETIK", "8"))
    try:
        async with httpx.AsyncClient(timeout=batas) as klien:
            jawab = await klien.post(
                url,
                json=badan,
                headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
            )
        jawab.raise_for_status()
        isi = jawab.json()["choices"][0]["message"]["content"]
        hasil = json.loads(isi)
        return hasil if isinstance(hasil, dict) else None
    except Exception as galat:  # jaringan, kuota, JSON rusak: semuanya jatuh ke templat
        log.warning("LLM gagal, pakai templat: %s", type(galat).__name__)
        return None
