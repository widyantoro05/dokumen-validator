"""
tests/test_readers_and_extractor.py - Tes untuk pdf_reader, ocr_engine, field_extractor, excel_reader.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from validator_dokumen.core.excel_reader import baca_beberapa_sheet, daftar_sheet
from validator_dokumen.core.field_extractor import (
    ekstrak_field_area,
    ekstrak_field_label,
    ekstrak_field_pola,
    ekstrak_semua_field,
)
from validator_dokumen.core.models import DefinisiField, SumberData
from validator_dokumen.core.pdf_reader import (
    baca_pdf,
    ekstrak_teks_semua_halaman,
    render_halaman_preview,
)
from validator_dokumen.core.ocr_engine import (
    cari_tesseract,
    ocr_halaman,
    praproses_gambar,
)
from validator_dokumen.core.normalizer import koreksi_karakter_ocr


class TestFieldExtractor:
    def test_ekstrak_label(self) -> None:
        teks = "Nomor Izin: IZN-1234-XYZ\nNama Perusahaan: PT Maju Jaya"
        res = ekstrak_field_label(teks, {"label": "Nomor Izin"})
        assert res == ["IZN-1234-XYZ"]

    def test_ekstrak_pola(self) -> None:
        teks = "Dokumen NIB: 1234567890123 berlaku aktif"
        res = ekstrak_field_pola(teks, {"pola": r"NIB:\s*(\d{13})"})
        assert res == ["1234567890123"]

    def test_ekstrak_area(self) -> None:
        hal_data = {
            "kata_kata": [
                {"teks": "PT", "kotak": (10, 10, 30, 25)},
                {"teks": "Maju", "kotak": (35, 10, 70, 25)},
                {"teks": "Jauh", "kotak": (400, 400, 450, 420)},
            ]
        }
        res = ekstrak_field_area(hal_data, {"x0_persen": 0, "y0_persen": 0, "x1_persen": 30, "y1_persen": 10}, 500, 500)
        assert res == ["PT Maju"]

    def test_ekstrak_semua_field(self) -> None:
        baca_res = {
            "halaman": [
                {
                    "nomor": 1,
                    "teks": "Nomor Izin: 123-ABC\nNIB: 9876543210123\nTabel:\nKolomTarget\nNilaiDalamTabel",
                    "sumber": "TEKS",
                    "confidence_rata": 100.0,
                }
            ]
        }
        defs = [
            DefinisiField("1", "no_izin", "label", {"label": "Nomor Izin"}),
            DefinisiField("2", "nib", "pola", {"pola": r"NIB:\s*(\d+)"}),
            DefinisiField("3", "tabel_f", "kolom_tabel", {"nama_kolom": "KolomTarget"}),
        ]
        hasil = ekstrak_semua_field(defs, baca_res)
        assert len(hasil) == 3
        assert hasil[0].nilai_mentah == "123-ABC"
        assert hasil[1].nilai_mentah == "9876543210123"
        assert hasil[2].nilai_mentah == "NilaiDalamTabel"


class TestPdfReader:
    def test_baca_pdf_teks(self) -> None:
        pdf_path = Path("tests/data/pdf_benar.pdf")
        if not pdf_path.exists():
            pytest.skip("Data PDF belum ada")
        hasil = baca_pdf(pdf_path)
        assert hasil["bisa_dibaca"] is True
        assert hasil["jumlah_halaman"] >= 1
        teks = ekstrak_teks_semua_halaman(hasil)
        assert "Nomor Izin" in teks

    def test_baca_pdf_rusak(self) -> None:
        pdf_path = Path("tests/data/pdf_rusak.pdf")
        if not pdf_path.exists():
            pytest.skip("Data PDF rusak belum ada")
        hasil = baca_pdf(pdf_path)
        assert hasil["bisa_dibaca"] is False
        assert "rusak" in hasil["error"].lower() or "tidak valid" in hasil["error"].lower()

    def test_baca_pdf_tidak_ada(self) -> None:
        hasil = baca_pdf(Path("tests/data/tidak_ada_file.pdf"))
        assert hasil["bisa_dibaca"] is False

    def test_render_preview(self) -> None:
        pdf_path = Path("tests/data/pdf_benar.pdf")
        if not pdf_path.exists():
            pytest.skip("Data PDF belum ada")
        img = render_halaman_preview(pdf_path, 0)
        assert img is not None


class TestExcelReader:
    def test_excel_reader(self) -> None:
        rekap_path = Path("tests/data/rekapan.xlsx")
        if not rekap_path.exists():
            pytest.skip("Data rekapan belum ada")
        sheets = daftar_sheet(rekap_path)
        assert len(sheets) >= 1
        tabel = baca_beberapa_sheet(rekap_path, sheets[:1])
        assert len(tabel.baris) >= 200

        # Test error branches
        assert daftar_sheet(Path("file_tidak_ada.xlsx")) == []
        with pytest.raises(ValueError):
            baca_beberapa_sheet(Path("file_tidak_ada.xlsx"), ["SheetX"])


class TestDecisionTrace:
    def test_ringkasan_jejak(self) -> None:
        from validator_dokumen.core.decision_trace import (
            buat_langkah,
            jejak_aturan,
            jejak_normalisasi,
            jejak_pencocokan,
            ringkasan_jejak,
        )
        l1 = jejak_normalisasi("PT Maju", "maju", ["abaikan_awalan"])
        l2 = jejak_pencocokan("A", "A", "Persis", True, 100.0)
        l3 = jejak_aturan("wajib", "val", True)
        ringkasan = ringkasan_jejak((l1, l2, l3))
        assert "normalisasi" in ringkasan
        assert "pencocokan" in ringkasan
        assert "aturan" in ringkasan
