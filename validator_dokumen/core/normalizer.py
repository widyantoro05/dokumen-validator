"""
core/normalizer.py - Fungsi normalisasi teks murni dan mudah dites.

Semua fungsi adalah fungsi murni (pure function): tidak ada efek samping,
input sama selalu menghasilkan output sama. Setiap opsi bisa dinyalakan
secara independen per pasangan pencocokan.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from validator_dokumen.core.constants import (
    BUSINESS_PREFIXES,
    DATE_FORMAT_DEFAULT,
    OCR_CHAR_MAP,
)
from validator_dokumen.core.models import OpsiNormalisasi

# ── Pola teks yang sudah dikompilasi (efisiensi) ─────────────────────────────

_POLA_TANDA_BACA = re.compile(r"[^\w\s]", re.UNICODE)
_POLA_SPASI_GANDA = re.compile(r"\s+")
_POLA_NOL_DEPAN = re.compile(r"(?<!\d)0+(\d)")
_POLA_BADAN_USAHA = re.compile(
    "|".join(BUSINESS_PREFIXES),
    re.IGNORECASE | re.UNICODE,
)

# Karakter tak terlihat yang dihapus
_KARAKTER_TAK_TERLIHAT = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\ufeff",  # BOM
    "\u00a0",  # non-breaking space
    "\u00ad",  # soft hyphen
}

# Pola tanggal Indonesia yang didukung
_BULAN_INDO: dict[str, int] = {
    "januari": 1,
    "jan": 1,
    "februari": 2,
    "feb": 2,
    "maret": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "mei": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "agustus": 8,
    "agt": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "desember": 12,
    "des": 12,
    "dec": 12,
}

_POLA_TANGGAL_TEKS = re.compile(
    r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)
_POLA_TANGGAL_NUMERIK = re.compile(
    r"(\d{1,4})[-/.](\d{1,2})[-/.](\d{2,4})",
)


# ══════════════════════════════════════════════════════════════════════════════
# FUNGSI NORMALISASI TEKS
# ══════════════════════════════════════════════════════════════════════════════


def hapus_karakter_tak_terlihat(teks: str) -> str:
    """Hapus karakter zero-width, NBSP, BOM, dan karakter tak terlihat lainnya."""
    return "".join(c for c in teks if c not in _KARAKTER_TAK_TERLIHAT)


def normalisasi_unicode(teks: str) -> str:
    """Normalisasi bentuk Unicode ke NFC (komposisi penuh)."""
    return unicodedata.normalize("NFC", teks)


def trim_spasi(teks: str) -> str:
    """Trim spasi depan/belakang dan ganti spasi ganda dengan satu spasi."""
    return _POLA_SPASI_GANDA.sub(" ", teks.strip())


def abaikan_huruf_besar(teks: str) -> str:
    """Ubah ke huruf kecil."""
    return teks.lower()


def hapus_tanda_baca_dan_spasi(teks: str) -> str:
    """Hapus semua tanda baca dan spasi (untuk perbandingan ketat)."""
    tanpa_baca = _POLA_TANDA_BACA.sub("", teks)
    return tanpa_baca.replace(" ", "")


def hapus_awalan_badan_usaha(teks: str) -> str:
    """
    Hapus awalan/akhiran badan usaha: PT, CV, UD, PD, Tbk, Persero.
    Contoh: "PT. Maju Jaya Tbk" -> "Maju Jaya"
    """
    hasil = _POLA_BADAN_USAHA.sub("", teks)
    return trim_spasi(hasil)


def hapus_nol_depan(teks: str) -> str:
    """
    Hapus nol di depan angka.
    Contoh: "00123" -> "123", "007" -> "7"
    """
    return _POLA_NOL_DEPAN.sub(r"\1", teks)


def koreksi_karakter_ocr(teks: str) -> str:
    """
    Koreksi karakter yang sering salah baca OCR.
    O->0, I/l->1, S->5, B->8, Z->2.
    Hanya berlaku pada konteks angka (di antara angka).
    """
    hasil = list(teks)
    for i, kar in enumerate(hasil):
        # Hanya koreksi jika karakter adalah huruf yang sering salah baca OCR
        # dan karakter di kiri/kanan adalah angka (konteks angka)
        if kar in OCR_CHAR_MAP:
            kiri_angka = i > 0 and hasil[i - 1].isdigit()
            kanan_angka = i < len(hasil) - 1 and hasil[i + 1].isdigit()
            if kiri_angka or kanan_angka:
                hasil[i] = OCR_CHAR_MAP[kar]
    return "".join(hasil)


def normalisasi_teks(teks: str, opsi: OpsiNormalisasi) -> str:
    """
    Terapkan normalisasi lengkap sesuai opsi yang dinyalakan.
    Urutan operasi deterministik.

    Args:
        teks: Teks yang akan dinormalisasi.
        opsi: Opsi normalisasi yang aktif.

    Returns:
        Teks ternormalisasi.
    """
    hasil = normalisasi_unicode(teks)

    if opsi.hapus_karakter_tak_terlihat:
        hasil = hapus_karakter_tak_terlihat(hasil)

    # Trim selalu dilakukan sebagai langkah dasar
    hasil = trim_spasi(hasil)

    if opsi.koreksi_ocr:
        hasil = koreksi_karakter_ocr(hasil)

    if opsi.abaikan_awalan_badan_usaha:
        hasil = hapus_awalan_badan_usaha(hasil)

    if opsi.abaikan_nol_depan:
        hasil = hapus_nol_depan(hasil)

    if opsi.abaikan_tanda_baca:
        hasil = hapus_tanda_baca_dan_spasi(hasil)
    elif opsi.abaikan_spasi:
        # Jika tanda baca tidak dihapus tapi spasi dihapus
        hasil = hasil.replace(" ", "")

    if opsi.abaikan_huruf_besar:
        hasil = abaikan_huruf_besar(hasil)

    return hasil


# ══════════════════════════════════════════════════════════════════════════════
# PARSER ANGKA
# ══════════════════════════════════════════════════════════════════════════════


def parse_angka(teks: str) -> Decimal | None:
    """
    Parse angka dari teks dengan format Indonesia atau internasional.

    Format yang didukung:
    - "1.000.000,50" (Indonesia: titik ribuan, koma desimal)
    - "1,000,000.50" (Internasional: koma ribuan, titik desimal)
    - "1000000" (tanpa pemisah)

    Returns:
        Decimal jika berhasil di-parse, None jika gagal.
    """
    if not teks or not teks.strip():
        return None

    bersih = teks.strip()

    # Deteksi format: jika ada koma dan titik, tentukan mana desimal
    ada_koma = "," in bersih
    ada_titik = "." in bersih

    try:
        if ada_koma and ada_titik:
            # Tentukan berdasarkan posisi terakhir pemisah
            pos_koma = bersih.rfind(",")
            pos_titik = bersih.rfind(".")
            if pos_koma > pos_titik:
                # Format Indonesia: 1.000,50
                bersih = bersih.replace(".", "").replace(",", ".")
            else:
                # Format internasional: 1,000.50
                bersih = bersih.replace(",", "")
        elif ada_koma:
            # Hanya koma: anggap desimal Indonesia jika di posisi -3 atau lebih
            if bersih.rfind(",") >= len(bersih) - 4:
                bersih = bersih.replace(",", ".")
            else:
                bersih = bersih.replace(",", "")
        # Jika hanya titik: anggap desimal internasional (tidak ubah)

        # Bersihkan karakter non-numerik selain titik dan minus
        bersih_final = re.sub(r"[^\d.\-]", "", bersih)
        return Decimal(bersih_final)
    except InvalidOperation:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PARSER TANGGAL
# ══════════════════════════════════════════════════════════════════════════════


def parse_tanggal(
    teks: str,
    format_default: str = DATE_FORMAT_DEFAULT,
) -> tuple[int, int, int] | None:
    """
    Parse tanggal dari teks ke tuple (tahun, bulan, hari).

    Format yang didukung:
    - "12 Januari 2025" / "12 Jan 2025" (teks Indonesia)
    - "12/01/2025", "12-01-2025" (numerik, urutan dari format_default)
    - "2025-01-12" (ISO, selalu tahun di kiri)

    Args:
        teks: Teks yang mengandung tanggal.
        format_default: Urutan komponen numerik ("dd/mm/yyyy" atau "mm/dd/yyyy").

    Returns:
        Tuple (tahun, bulan, hari) atau None jika gagal.
    """
    if not teks or not teks.strip():
        return None

    bersih = teks.strip()

    # Coba format teks Indonesia dulu
    m = _POLA_TANGGAL_TEKS.search(bersih)
    if m:
        hari_str, bulan_str, tahun_str = m.groups()
        bulan_key = bulan_str.lower()
        if bulan_key in _BULAN_INDO:
            try:
                return (int(tahun_str), _BULAN_INDO[bulan_key], int(hari_str))
            except ValueError:
                pass

    # Coba format numerik
    m2 = _POLA_TANGGAL_NUMERIK.search(bersih)
    if m2:
        a_str, b_str, c_str = m2.groups()
        a, b, c = int(a_str), int(b_str), int(c_str)

        # ISO: jika a > 31, pasti tahun
        if a > 31:
            return (a, b, c)

        # Gunakan format_default untuk komponen ambigu
        if format_default.startswith("dd"):
            # dd/mm/yyyy
            if c < 100:
                c += 2000  # 2 digit tahun
            return (c, b, a)
        else:
            # mm/dd/yyyy
            if c < 100:
                c += 2000
            return (c, a, b)

    return None


def bandingkan_tanggal(
    teks_a: str,
    teks_b: str,
    mode: str = "sama",
    format_default: str = DATE_FORMAT_DEFAULT,
) -> bool | None:
    """
    Bandingkan dua tanggal.

    Args:
        teks_a: Tanggal pertama (nilai dokumen).
        teks_b: Tanggal kedua (nilai rekapan).
        mode: "sama" | "a_lebih_kecil" | "a_lebih_besar"
        format_default: Urutan komponen numerik.

    Returns:
        True/False jika bisa dibandingkan, None jika gagal parse.
    """
    tgl_a = parse_tanggal(teks_a, format_default)
    tgl_b = parse_tanggal(teks_b, format_default)
    if tgl_a is None or tgl_b is None:
        return None

    if mode == "sama":
        return tgl_a == tgl_b
    elif mode == "a_lebih_kecil":
        return tgl_a <= tgl_b
    elif mode == "a_lebih_besar":
        return tgl_a >= tgl_b
    return None
