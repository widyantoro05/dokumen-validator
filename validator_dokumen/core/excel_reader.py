"""
core/excel_reader.py - Alias dan utilitas untuk pembacaan Excel.

Wrapper tipis di atas recap_table.baca_excel dengan fungsi tambahan
untuk mendukung beberapa file/sheet dan pratinjau tabel.
"""

from __future__ import annotations

from pathlib import Path

from validator_dokumen.core.models import TabelRekap
from validator_dokumen.core.recap_table import baca_excel, gabung_tabel


def daftar_sheet(path: Path) -> list[str]:
    """
    Dapatkan daftar nama sheet dari file Excel.

    Args:
        path: Path ke file Excel.

    Returns:
        Daftar nama sheet.
    """
    try:
        import openpyxl  # type: ignore[import-untyped]

        wb = openpyxl.load_workbook(str(path), read_only=True)
        sheets = list(wb.sheetnames)
        wb.close()
        return sheets
    except Exception:
        return []


def baca_beberapa_sheet(
    path: Path,
    sheet_list: list[str] | None = None,
    baris_header: int = 1,
) -> TabelRekap:
    """
    Baca beberapa sheet dari satu file Excel dan gabungkan.

    Args:
        path: Path file Excel.
        sheet_list: Daftar nama sheet, None = semua sheet.
        baris_header: Nomor baris header (1-based).

    Returns:
        TabelRekap gabungan.
    """
    if sheet_list is None:
        sheet_list = daftar_sheet(path)

    tabel_list: list[TabelRekap] = []
    for sheet in sheet_list:
        try:
            tabel = baca_excel(path, sheet, baris_header)
            tabel_list.append(tabel)
        except Exception:
            continue

    if not tabel_list:
        raise ValueError(f"Tidak bisa membaca sheet apapun dari {path}")

    return gabung_tabel(tabel_list)
