"""
utils/paths.py - Utilitas path yang aman untuk Windows dan PyInstaller.
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relatif: str) -> Path:
    """
    Dapatkan path absolut ke resource.
    Aman untuk PyInstaller (sys._MEIPASS) dan mode development.

    Args:
        relatif: Path relatif dari root proyek atau bundle.

    Returns:
        Path absolut.
    """
    if getattr(sys, "frozen", False):
        # Mode PyInstaller bundle
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # Mode development - root proyek
        base = Path(__file__).parent.parent.parent

    return base / relatif


def folder_profil() -> Path:
    """Dapatkan folder profil."""
    return resource_path("profiles")


def folder_app_data() -> Path:
    """Dapatkan folder data aplikasi di AppData dengan fallback tempdir."""
    import os
    base_env = os.environ.get("LOCALAPPDATA")
    if base_env:
        base = Path(base_env) / "ValidatorDokumen"
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except (PermissionError, OSError):
            pass
    import tempfile
    fallback = Path(tempfile.gettempdir()) / "ValidatorDokumen"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback
