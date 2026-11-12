"""Bayesian Knowledge Tracing: rumus saja, tanpa penyimpanan."""

from .kurikulum import ParamBKT


def perkiraan_berhasil(p: float, param: ParamBKT) -> float:
    """Peluang percobaan berikutnya berhasil."""
    return p * (1 - param.salah) + (1 - p) * param.tebak


def perbarui(p: float, berhasil: bool, param: ParamBKT) -> float:
    """Penguasaan baru setelah satu percobaan."""
    if berhasil:
        atas = p * (1 - param.salah)
        bawah = atas + (1 - p) * param.tebak
    else:
        atas = p * param.salah
        bawah = atas + (1 - p) * (1 - param.tebak)
    pasca = atas / bawah if bawah > 0 else p
    return pasca + (1 - pasca) * param.belajar


def luruh(p: float, awal: float, hari: float, paruh_hari: float) -> float:
    """Penguasaan turun pelan menuju nilai awalnya sejak latihan terakhir."""
    if hari <= 0 or p <= awal:
        return p
    return awal + (p - awal) * 0.5 ** (hari / paruh_hari)
