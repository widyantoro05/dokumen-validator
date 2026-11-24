"""
core/audit_log.py - Log audit untuk override manual status dan perubahan konfigurasi.

Log ditulis secara atomik ke log_audit.txt di folder output.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from validator_dokumen.core.constants import OUTPUT_ENCODING
from validator_dokumen.core.models import StatusValidasi


def _nama_pengguna_windows() -> str:
    """Dapatkan nama pengguna Windows saat ini."""
    return os.environ.get("USERNAME", os.environ.get("USER", "tidak_diketahui"))


def tulis_log_audit(
    folder_output: Path,
    nama_file: str,
    status_lama: StatusValidasi,
    status_baru: StatusValidasi,
    catatan: str,
) -> None:
    """
    Catat override manual status ke log_audit.txt.

    Args:
        folder_output: Folder hasil validasi.
        nama_file: Nama file PDF yang di-override.
        status_lama: Status sebelum override.
        status_baru: Status baru.
        catatan: Catatan wajib dari pengguna.
    """
    path_log = folder_output / "log_audit.txt"

    waktu = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    pengguna = _nama_pengguna_windows()

    baris = (
        f"[{waktu}] OVERRIDE oleh {pengguna}\n"
        f"  File: {nama_file}\n"
        f"  Status: {status_lama.value} -> {status_baru.value}\n"
        f"  Catatan: {catatan}\n"
        f"{'=' * 60}\n"
    )

    # Append ke log yang ada
    with path_log.open("a", encoding=OUTPUT_ENCODING) as f:
        f.write(baris)
