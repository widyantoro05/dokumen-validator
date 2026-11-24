"""
core/constants.py - Semua konstanta aplikasi Validator Dokumen.
Tidak ada angka ajaib di tempat lain; semua ambang didefinisikan di sini
atau di profil pengguna (profil menang jika ada).
"""

from __future__ import annotations

# ── Versi ────────────────────────────────────────────────────────────────────
APP_VERSION: str = "1.0.0"
PROFILE_SCHEMA_VERSION: int = 1

# ── OCR ──────────────────────────────────────────────────────────────────────
OCR_DPI: int = 300  # resolusi render halaman untuk OCR
OCR_CONFIDENCE_MIN: float = 80.0  # batas bawah confidence OCR (0-100)
OCR_CHAR_THRESHOLD: int = 30  # jika karakter < ini, halaman dianggap gambar
OCR_LANG: str = "ind+eng"  # bahasa Tesseract

# ── Fuzzy matching ───────────────────────────────────────────────────────────
FUZZY_DEFAULT_THRESHOLD: float = 90.0  # ambang default kesamaan (persen)
FUZZY_NEAR_MISS_DECREMENT: int = 2  # kurangi K sebesar ini untuk "hampir cocok"

# ── Skor ─────────────────────────────────────────────────────────────────────
SCORE_MIN_GAP: int = 1  # selisih skor minimum antara peringkat 1 dan 2 agar tidak ambigu

# ── Desimal & tanggal ────────────────────────────────────────────────────────
DATE_FORMAT_DEFAULT: str = "dd/mm/yyyy"  # urutan parsing tanggal ambigu
NUMERIC_TOLERANCE_DEFAULT: float = 0.0  # toleransi selisih numerik default

# ── OCR koreksi karakter ─────────────────────────────────────────────────────
OCR_CHAR_MAP: dict[str, str] = {
    "O": "0",
    "I": "1",
    "l": "1",
    "S": "5",
    "B": "8",
    "Z": "2",
}

# ── Awalan/akhiran badan usaha yang diabaikan saat normalisasi ───────────────
BUSINESS_PREFIXES: list[str] = [
    r"\bPT\.?\s*",
    r"\bCV\.?\s*",
    r"\bUD\.?\s*",
    r"\bPD\.?\s*",
    r"\bTbk\.?\s*",
    r"\bPersero\s*",
]

# ── Path Tesseract (dicari berurutan) ─────────────────────────────────────────
TESSERACT_SEARCH_PATHS: list[str] = [
    "tesseract",  # folder di samping exe / bundle
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

# ── Performa ──────────────────────────────────────────────────────────────────
PARALLEL_WORKERS_DEFAULT: int = -1  # -1 = jumlah core - 1
PAGE_IMAGE_CACHE_SIZE: int = 20  # maks halaman di LRU cache pratinjau

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_ENCODING: str = "utf-8-sig"  # UTF-8 dengan BOM agar benar di Notepad Windows
OUTPUT_DATE_FORMAT: str = "%Y%m%d_%H%M%S"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB per file log
LOG_BACKUP_COUNT: int = 5

# ── UI ────────────────────────────────────────────────────────────────────────
UI_BATCH_UPDATE_MS: int = 100  # interval update tabel dari worker (ms)
UI_MIN_WIDTH: int = 1280
UI_MIN_HEIGHT: int = 720
