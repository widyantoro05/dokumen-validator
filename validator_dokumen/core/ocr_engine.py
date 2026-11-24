"""
core/ocr_engine.py - Mesin OCR menggunakan Tesseract via pytesseract.

Fitur:
- Cari Tesseract secara otomatis di beberapa lokasi
- Pra-pemrosesan gambar: grayscale, threshold adaptif, deskew, denoise
- Cache hasil OCR ke disk berdasarkan hash file+halaman+pengaturan
- Render halaman PDF ke gambar dengan DPI yang dikonfigurasi
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from validator_dokumen.core.constants import (
    OCR_CONFIDENCE_MIN,
    OCR_DPI,
    OCR_LANG,
    TESSERACT_SEARCH_PATHS,
)


# ── Lokasi cache OCR ──────────────────────────────────────────────────────────
def _folder_cache_ocr() -> Path:
    """Dapatkan folder cache OCR di LOCALAPPDATA dengan fallback tempdir."""
    base_env = os.environ.get("LOCALAPPDATA")
    if base_env:
        base = Path(base_env) / "ValidatorDokumen" / "ocr_cache"
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except (PermissionError, OSError):
            pass
    import tempfile

    fallback = Path(tempfile.gettempdir()) / "ValidatorDokumen" / "ocr_cache"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


# ── Cari Tesseract ────────────────────────────────────────────────────────────
def cari_tesseract() -> str | None:
    """
    Cari path executable Tesseract secara berurutan:
    1. Folder tesseract/ di samping exe atau dalam bundle
    2. C:\\Program Files\\Tesseract-OCR
    3. PATH sistem

    Returns:
        Path ke tesseract.exe atau None jika tidak ditemukan.
    """
    # Lokasi 1: bundle PyInstaller atau samping skrip
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent.parent

    for kandidat in TESSERACT_SEARCH_PATHS:
        # Relatif ke base_dir
        path_relatif = base_dir / kandidat
        if path_relatif.exists():
            return str(path_relatif)

        # Path absolut
        path_abs = Path(kandidat)
        if path_abs.exists():
            return str(path_abs)

    # PATH sistem
    import shutil

    path_sistem = shutil.which("tesseract")
    if path_sistem:
        return path_sistem

    return None


def inisialisasi_tesseract() -> bool:
    """
    Set pytesseract.tesseract_cmd ke path yang ditemukan.

    Returns:
        True jika berhasil, False jika Tesseract tidak ditemukan.
    """
    try:
        import pytesseract  # type: ignore[import-untyped]
    except ImportError:
        return False

    path = cari_tesseract()
    if not path:
        return False

    pytesseract.pytesseract.tesseract_cmd = path

    # Set TESSDATA_PREFIX jika ada
    tessdata = Path(path).parent / "tessdata"
    if tessdata.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata.parent)

    return True


# ── Pra-pemrosesan gambar ─────────────────────────────────────────────────────
def praproses_gambar(gambar_array: Any) -> Any:
    """
    Pra-pemrosesan gambar untuk meningkatkan akurasi OCR.
    Langkah: grayscale -> denoise -> threshold adaptif -> deskew.

    Args:
        gambar_array: numpy array gambar (dari cv2 atau PIL).

    Returns:
        numpy array gambar yang sudah diproses.
    """
    try:
        import cv2  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]
    except ImportError:
        return gambar_array

    img = gambar_array

    # Konversi ke grayscale jika belum
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise
    img = cv2.fastNlMeansDenoising(img, h=10)

    # Threshold adaptif (lebih baik untuk dokumen dengan cahaya tidak rata)
    img = cv2.adaptiveThreshold(
        img,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )

    # Deskew (koreksi kemiringan)
    img = _deskew(img, cv2, np)

    return img


def _deskew(img: Any, cv2: Any, np: Any) -> Any:
    """Koreksi kemiringan dokumen menggunakan transformasi affine."""
    try:
        # Deteksi sudut kemiringan
        coords = np.column_stack(np.where(img < 128))
        if len(coords) < 10:
            return img

        angle = cv2.minAreaRect(coords)[-1]

        # Koreksi sudut
        angle = -(90 + angle) if angle < -45 else -angle

        # Jangan koreksi jika sudut sangat kecil
        if abs(angle) < 0.5:
            return img

        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return img


# ── OCR satu halaman ──────────────────────────────────────────────────────────
def ocr_halaman(
    gambar_array: Any,
    lang: str = OCR_LANG,
    confidence_min: float = OCR_CONFIDENCE_MIN,
) -> dict[str, Any]:
    """
    Jalankan OCR pada satu halaman (numpy array gambar).

    Returns:
        Dict berisi:
        - teks: str (teks gabungan)
        - kata_kata: list[dict] (kata, confidence, kotak)
        - confidence_rata: float
        - meragukan: bool
    """
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError as e:
        return {
            "teks": "",
            "kata_kata": [],
            "confidence_rata": 0.0,
            "meragukan": True,
            "error": str(e),
        }

    # Pra-pemrosesan
    img_proses = praproses_gambar(gambar_array)

    # Konversi ke PIL Image
    pil_img = Image.fromarray(img_proses)

    try:
        # Dapatkan data detail per kata
        data = pytesseract.image_to_data(
            pil_img,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )
    except Exception as e:
        return {
            "teks": "",
            "kata_kata": [],
            "confidence_rata": 0.0,
            "meragukan": True,
            "error": str(e),
        }

    kata_kata = []
    conf_list = []

    for i in range(len(data["text"])):
        teks_kata = data["text"][i].strip()
        if not teks_kata:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0

        if conf < 0:
            continue

        conf_list.append(conf)
        kata_kata.append(
            {
                "teks": teks_kata,
                "confidence": conf,
                "kotak": (
                    data["left"][i],
                    data["top"][i],
                    data["left"][i] + data["width"][i],
                    data["top"][i] + data["height"][i],
                ),
                "halaman": data.get("page_num", [0] * len(data["text"]))[i],
            }
        )

    teks_gabungan = " ".join(k["teks"] for k in kata_kata)
    conf_rata = sum(conf_list) / len(conf_list) if conf_list else 0.0
    meragukan = conf_rata < confidence_min

    return {
        "teks": teks_gabungan,
        "kata_kata": kata_kata,
        "confidence_rata": conf_rata,
        "meragukan": meragukan,
    }


# ── Cache OCR ─────────────────────────────────────────────────────────────────
def _kunci_cache(hash_file: str, nomor_halaman: int, pengaturan: dict[str, Any]) -> str:
    """Buat kunci cache unik berdasarkan hash file, halaman, dan pengaturan."""
    pengaturan_str = json.dumps(pengaturan, sort_keys=True)
    gabungan = f"{hash_file}:{nomor_halaman}:{pengaturan_str}"
    return hashlib.sha256(gabungan.encode()).hexdigest()


def simpan_cache(kunci: str, hasil: dict[str, Any]) -> None:
    """Simpan hasil OCR ke cache disk."""
    try:
        path = _folder_cache_ocr() / f"{kunci}.json"
        path_tmp = path.with_suffix(".tmp")
        path_tmp.write_text(json.dumps(hasil, ensure_ascii=False), encoding="utf-8")
        path_tmp.replace(path)
    except Exception:
        pass  # Kegagalan cache tidak fatal


def muat_cache(kunci: str) -> dict[str, Any] | None:
    """Muat hasil OCR dari cache disk. Returns None jika tidak ada."""
    try:
        path = _folder_cache_ocr() / f"{kunci}.json"
        if path.exists():
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def ocr_halaman_dengan_cache(
    gambar_array: Any,
    hash_file: str,
    nomor_halaman: int,
    pengaturan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    OCR dengan cache: coba muat dari cache dulu, baru jalankan OCR.

    Args:
        gambar_array: numpy array gambar.
        hash_file: Hash SHA-256 file PDF.
        nomor_halaman: Nomor halaman (0-based).
        pengaturan: Pengaturan OCR (lang, confidence_min, dll.).

    Returns:
        Hasil OCR (sama seperti ocr_halaman()).
    """
    if pengaturan is None:
        pengaturan = {"lang": OCR_LANG, "dpi": OCR_DPI}

    kunci = _kunci_cache(hash_file, nomor_halaman, pengaturan)
    hasil_cache = muat_cache(kunci)
    if hasil_cache is not None:
        return hasil_cache

    hasil = ocr_halaman(
        gambar_array,
        lang=pengaturan.get("lang", OCR_LANG),
        confidence_min=pengaturan.get("confidence_min", OCR_CONFIDENCE_MIN),
    )
    simpan_cache(kunci, hasil)
    return hasil
