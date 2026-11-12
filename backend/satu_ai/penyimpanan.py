"""Penyimpanan status Otak per anak.

Versi ini menyimpan di memori, cukup untuk pengembangan dan demo satu proses.
Untuk produksi, buat kelas dengan dua metode yang sama (muat, simpan) yang
menulis StatusAnak.ke_dict() ke satu kolom JSON di tabel anak.
"""

from typing import Protocol

from .otak import StatusAnak


class Penyimpanan(Protocol):
    def muat(self, anak_id: str) -> StatusAnak: ...

    def simpan(self, anak_id: str, status: StatusAnak) -> None: ...


class PenyimpananMemori:
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    def muat(self, anak_id: str) -> StatusAnak:
        return StatusAnak.dari_dict(self._data.get(anak_id, {}))

    def simpan(self, anak_id: str, status: StatusAnak) -> None:
        self._data[anak_id] = status.ke_dict()
