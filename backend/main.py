"""Menjalankan lapis AI sendirian untuk pengembangan:

    uvicorn main:app --reload --port 8000

Dokumentasi endpoint otomatis ada di http://localhost:8000/docs
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from satu_ai.api import buat_router

app = FastAPI(title="SATU - lapis AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ASAL_DIIZINKAN", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(buat_router())
