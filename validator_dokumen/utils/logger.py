"""
utils/logger.py - Konfigurasi logging terpusat dengan RotatingFileHandler.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from validator_dokumen.core.constants import LOG_BACKUP_COUNT, LOG_MAX_BYTES


def _folder_log() -> Path:
    """Dapatkan folder log di %LOCALAPPDATA%\\ValidatorDokumen\\logs dengan fallback tempdir."""
    base_env = os.environ.get("LOCALAPPDATA")
    if base_env:
        base = Path(base_env) / "ValidatorDokumen" / "logs"
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except (PermissionError, OSError):
            pass
    import tempfile
    fallback = Path(tempfile.gettempdir()) / "ValidatorDokumen" / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def setup_logging(nama_app: str = "ValidatorDokumen", level: int = logging.INFO) -> logging.Logger:
    """
    Konfigurasi logging dengan RotatingFileHandler dan StreamHandler.

    Returns:
        Logger utama aplikasi.
    """
    logger = logging.getLogger(nama_app)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler file
    path_log = _folder_log() / f"{nama_app}.log"
    fh = RotatingFileHandler(
        str(path_log),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Handler konsol (untuk CLI)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)
    logger.addHandler(sh)

    return logger


def setup_global_exception_handler(logger: logging.Logger) -> None:
    """
    Pasang handler global untuk exception tak tertangkap.
    Log stack trace ke file log. Panggil sebelum loop UI dimulai.
    """
    def handler(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:  # type: ignore[name-defined]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Exception tak tertangkap:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

    sys.excepthook = handler  # type: ignore[assignment]


# Logger utama - dipakai di seluruh aplikasi
log = setup_logging()
