"""
core/decision_trace.py - Jejak keputusan (decision trace) untuk reproduksi & audit.

Setiap keputusan validasi direkam dalam jejak yang bisa ditampilkan di UI
("Kenapa hasilnya begini?") dan dimasukkan ke laporan.
"""

from __future__ import annotations

from validator_dokumen.core.models import LangkahJejak


def buat_langkah(
    langkah: str,
    keterangan: str,
    nilai_masuk: str = "",
    nilai_keluar: str = "",
    hasil: bool | None = None,
) -> LangkahJejak:
    """Factory untuk membuat satu langkah jejak keputusan."""
    return LangkahJejak(
        langkah=langkah,
        keterangan=keterangan,
        nilai_masuk=nilai_masuk,
        nilai_keluar=nilai_keluar,
        hasil=hasil,
    )


def ringkasan_jejak(jejak: tuple[LangkahJejak, ...]) -> str:
    """
    Buat ringkasan teks dari jejak keputusan untuk tampil di UI.

    Returns:
        String multi-baris yang bisa dibaca manusia.
    """
    baris: list[str] = []
    for i, langkah in enumerate(jejak, 1):
        status = ""
        if langkah.hasil is True:
            status = "✔"
        elif langkah.hasil is False:
            status = "✖"
        else:
            status = "ℹ"

        baris_teks = f"{i}. {status} [{langkah.langkah}] {langkah.keterangan}"
        if langkah.nilai_masuk or langkah.nilai_keluar:
            baris_teks += f"\n   Masuk: {langkah.nilai_masuk!r} -> Keluar: {langkah.nilai_keluar!r}"
        baris.append(baris_teks)

    return "\n".join(baris)


def jejak_normalisasi(
    nilai_mentah: str,
    nilai_ternormalisasi: str,
    opsi_aktif: list[str],
) -> LangkahJejak:
    """Buat langkah jejak untuk proses normalisasi."""
    opsi_str = ", ".join(opsi_aktif) if opsi_aktif else "tidak ada"
    return buat_langkah(
        langkah="normalisasi",
        keterangan=f"Opsi aktif: {opsi_str}",
        nilai_masuk=nilai_mentah,
        nilai_keluar=nilai_ternormalisasi,
    )


def jejak_pencocokan(
    nilai_dokumen: str,
    nilai_rekap: str,
    mode: str,
    cocok: bool,
    skor: float | None = None,
) -> LangkahJejak:
    """Buat langkah jejak untuk proses pencocokan."""
    keterangan = f"Mode: {mode}"
    if skor is not None:
        keterangan += f" | Skor kemiripan: {skor:.1f}%"
    return buat_langkah(
        langkah="pencocokan",
        keterangan=keterangan,
        nilai_masuk=f"Dokumen={nilai_dokumen!r} | Rekap={nilai_rekap!r}",
        nilai_keluar="COCOK" if cocok else "TIDAK COCOK",
        hasil=cocok,
    )


def jejak_aturan(
    nama_aturan: str,
    nilai: str,
    lolos: bool,
    keterangan: str = "",
) -> LangkahJejak:
    """Buat langkah jejak untuk penerapan satu aturan field."""
    return buat_langkah(
        langkah="aturan",
        keterangan=f"{nama_aturan}: {keterangan}",
        nilai_masuk=nilai,
        nilai_keluar="LOLOS" if lolos else "GAGAL",
        hasil=lolos,
    )
