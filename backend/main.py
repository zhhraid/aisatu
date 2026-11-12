"""Menjalankan lapis AI sendirian untuk pengembangan:

    python -m uvicorn main:app --port 8000

Pengaturan dibaca dari berkas .env di folder ini. Dokumentasi endpoint otomatis ada di
http://localhost:8000/docs, dan http://localhost:8000/ai/status menunjukkan pengaturan
mana yang belum terisi.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from satu_ai.api import buat_router
from satu_ai.pengaturan import muat_env

# Harus sebelum buat_router(), karena mode demo dibaca saat router dibuat.
muat_env(Path(__file__).resolve().parent)

app = FastAPI(title="SATU - lapis AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ASAL_DIIZINKAN", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(buat_router())


@app.get("/", include_in_schema=False)
def beranda() -> dict:
    return {"layanan": "SATU - lapis AI", "coba_endpoint": "/docs", "cek_pengaturan": "/ai/status"}
