"""
core/pdf_reader.py - Pembaca PDF: ekstraksi teks langsung dan OCR.

Strategi per halaman:
1. Ekstrak teks langsung dengan PyMuPDF
2. Jika karakter < threshold atau opsi "Paksa OCR", jalankan OCR
3. Tangani PDF rusak, terproteksi, dan kosong tanpa crash
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from validator_dokumen.core.constants import (
    OCR_CHAR_THRESHOLD,
    OCR_DPI,
    OCR_LANG,
)
from validator_dokumen.core.models import SumberData


def _hash_file_pdf(path: Path) -> str:
    """Hitung SHA-256 dari file PDF."""
    sha = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
    except OSError:
        pass
    return sha.hexdigest()


def baca_pdf(
    path: Path,
    paksa_ocr: bool = False,
    pengaturan_ocr: dict[str, Any] | None = None,
    callback_batal: Any = None,
) -> dict[str, Any]:
    """
    Baca satu file PDF. Ekstrak teks per halaman, OCR jika diperlukan.

    Args:
        path: Path ke file PDF.
        paksa_ocr: Jika True, selalu OCR semua halaman.
        pengaturan_ocr: Pengaturan OCR (lang, dpi, confidence_min).
        callback_batal: Callable yang mengembalikan True jika proses harus dibatalkan.

    Returns:
        Dict berisi:
        - halaman: list[dict] - data per halaman
        - hash_file: str
        - jumlah_halaman: int
        - error: str (kosong jika sukses)
        - bisa_dibaca: bool
    """
    if pengaturan_ocr is None:
        pengaturan_ocr = {}

    dpi = pengaturan_ocr.get("dpi", OCR_DPI)
    pengaturan_ocr.get("lang", OCR_LANG)

    if not path.exists():
        return {
            "halaman": [],
            "hash_file": "",
            "jumlah_halaman": 0,
            "error": f"File tidak ditemukan: {path}",
            "bisa_dibaca": False,
        }

    hash_file = _hash_file_pdf(path)

    try:
        import fitz  # type: ignore[import-untyped]  # PyMuPDF
    except ImportError:
        return {
            "halaman": [],
            "hash_file": hash_file,
            "jumlah_halaman": 0,
            "error": "PyMuPDF (fitz) tidak terinstal.",
            "bisa_dibaca": False,
        }

    try:
        doc = fitz.open(str(path))
    except fitz.FileDataError as e:
        return {
            "halaman": [],
            "hash_file": hash_file,
            "jumlah_halaman": 0,
            "error": f"PDF rusak atau tidak valid: {e}",
            "bisa_dibaca": False,
        }
    except Exception as e:
        return {
            "halaman": [],
            "hash_file": hash_file,
            "jumlah_halaman": 0,
            "error": f"Tidak bisa membuka PDF: {e}",
            "bisa_dibaca": False,
        }

    # Cek proteksi password
    if doc.is_encrypted:
        # Coba buka tanpa password (beberapa hanya proteksi metadata)
        if not doc.authenticate(""):
            doc.close()
            return {
                "halaman": [],
                "hash_file": hash_file,
                "jumlah_halaman": 0,
                "error": "PDF terproteksi password.",
                "bisa_dibaca": False,
            }

    jumlah_halaman = len(doc)
    if jumlah_halaman == 0:
        doc.close()
        return {
            "halaman": [],
            "hash_file": hash_file,
            "jumlah_halaman": 0,
            "error": "PDF kosong (tidak ada halaman).",
            "bisa_dibaca": False,
        }

    halaman_list: list[dict[str, Any]] = []

    for nomor_hal in range(jumlah_halaman):
        # Cek flag batal
        if callback_batal and callback_batal():
            doc.close()
            return {
                "halaman": halaman_list,
                "hash_file": hash_file,
                "jumlah_halaman": jumlah_halaman,
                "error": "Proses dibatalkan.",
                "bisa_dibaca": True,
            }

        page = doc[nomor_hal]
        data_halaman = _baca_halaman(
            page=page,
            nomor_hal=nomor_hal,
            hash_file=hash_file,
            paksa_ocr=paksa_ocr,
            dpi=dpi,
            pengaturan_ocr=pengaturan_ocr,
        )
        halaman_list.append(data_halaman)

    doc.close()

    return {
        "halaman": halaman_list,
        "hash_file": hash_file,
        "jumlah_halaman": jumlah_halaman,
        "error": "",
        "bisa_dibaca": True,
    }


def _baca_halaman(
    page: Any,
    nomor_hal: int,
    hash_file: str,
    paksa_ocr: bool,
    dpi: int,
    pengaturan_ocr: dict[str, Any],
) -> dict[str, Any]:
    """
    Baca satu halaman: ekstrak teks, OCR jika diperlukan.

    Returns:
        Dict berisi teks, kata_kata, sumber, confidence_rata, dll.
    """
    # Ekstrak teks langsung
    teks_langsung = page.get_text("text")
    kata_dengan_kotak: list[dict[str, Any]] = []

    if not paksa_ocr and len(teks_langsung.strip()) >= OCR_CHAR_THRESHOLD:
        # Gunakan teks langsung
        # Dapatkan kata dengan koordinat
        for blok in page.get_text("dict")["blocks"]:
            if blok.get("type") != 0:  # 0 = teks
                continue
            for baris in blok.get("lines", []):
                for span in baris.get("spans", []):
                    for kata in span.get("text", "").split():
                        if kata.strip():
                            kata_dengan_kotak.append(
                                {
                                    "teks": kata,
                                    "confidence": 100.0,
                                    "kotak": tuple(blok.get("bbox", (0, 0, 0, 0))),
                                    "halaman": nomor_hal + 1,
                                }
                            )

        return {
            "nomor": nomor_hal + 1,
            "teks": teks_langsung,
            "kata_kata": kata_dengan_kotak,
            "sumber": SumberData.TEKS.value,
            "confidence_rata": 100.0,
            "meragukan": False,
        }

    # Perlu OCR - render halaman ke gambar
    try:
        import numpy as np  # type: ignore[import-untyped]

        from validator_dokumen.core.ocr_engine import ocr_halaman_dengan_cache

        mat = page.get_pixmap(dpi=dpi)
        samples = mat.samples
        gambar = np.frombuffer(samples, dtype=np.uint8).reshape(mat.height, mat.width, mat.n)

        # Konversi dari fitz format ke BGR jika perlu
        gambar_final: Any = gambar
        if mat.n == 4:  # RGBA
            import cv2  # type: ignore[import-untyped]

            gambar_final = cv2.cvtColor(gambar, cv2.COLOR_RGBA2BGR)
        elif mat.n == 3:  # RGB
            import cv2

            gambar_final = cv2.cvtColor(gambar, cv2.COLOR_RGB2BGR)

        hasil_ocr = ocr_halaman_dengan_cache(
            gambar_array=gambar_final,
            hash_file=hash_file,
            nomor_halaman=nomor_hal,
            pengaturan=pengaturan_ocr,
        )

        return {
            "nomor": nomor_hal + 1,
            "teks": hasil_ocr.get("teks", ""),
            "kata_kata": hasil_ocr.get("kata_kata", []),
            "sumber": SumberData.OCR.value,
            "confidence_rata": hasil_ocr.get("confidence_rata", 0.0),
            "meragukan": hasil_ocr.get("meragukan", True),
        }
    except Exception as e:
        # Fallback: gunakan teks langsung meskipun kurang karakter
        return {
            "nomor": nomor_hal + 1,
            "teks": teks_langsung,
            "kata_kata": [],
            "sumber": SumberData.TEKS.value,
            "confidence_rata": 100.0,
            "meragukan": False,
            "error_ocr": str(e),
        }


def ekstrak_teks_semua_halaman(hasil_baca: dict[str, Any]) -> str:
    """Gabungkan teks dari semua halaman menjadi satu string."""
    return "\n\n".join(h.get("teks", "") for h in hasil_baca.get("halaman", []))


def render_halaman_preview(
    path: Path,
    nomor_halaman: int = 0,
    dpi: int = 150,
) -> Any | None:
    """
    Render satu halaman PDF untuk pratinjau UI.

    Args:
        path: Path ke file PDF.
        nomor_halaman: Nomor halaman (0-based).
        dpi: DPI render (lebih rendah untuk pratinjau).

    Returns:
        PIL Image atau None jika gagal.
    """
    try:
        import fitz  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]
        from PIL import Image  # type: ignore[import-untyped]

        doc = fitz.open(str(path))
        if nomor_halaman >= len(doc):
            doc.close()
            return None
        page = doc[nomor_halaman]
        mat = page.get_pixmap(dpi=dpi)
        samples = mat.samples
        gambar = np.frombuffer(samples, dtype=np.uint8).reshape(mat.height, mat.width, mat.n)
        doc.close()

        if mat.n == 4:
            return Image.fromarray(gambar, "RGBA").convert("RGB")
        elif mat.n == 3:
            return Image.fromarray(gambar, "RGB")
        else:
            return Image.fromarray(gambar)
    except Exception:
        return None
