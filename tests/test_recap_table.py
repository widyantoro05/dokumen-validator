"""
tests/test_recap_table.py - Tes unit untuk modul recap_table.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

from validator_dokumen.core.models import BarisRekap, OpsiNormalisasi, TabelRekap
from validator_dokumen.core.recap_table import (
    IndeksRekap,
    _normalisasi_header,
    baca_excel,
    gabung_tabel,
)


def _buat_baris(id_: str, data: dict[str, str]) -> BarisRekap:
    return BarisRekap(
        id=id_, data=data,
        sumber_file="tes.xlsx", sumber_sheet="Data", nomor_baris_asli=1,
    )


def _buat_tabel(baris_list: list[BarisRekap]) -> TabelRekap:
    kolom = tuple(baris_list[0].data.keys()) if baris_list else ()
    return TabelRekap(baris=tuple(baris_list), kolom=kolom, sumber_file="tes.xlsx", hash_file="abc")


def _buat_indeks(baris_list: list[BarisRekap], kolom: list[str]) -> IndeksRekap:
    tabel = _buat_tabel(baris_list)
    opsi = {k: OpsiNormalisasi(abaikan_huruf_besar=True, abaikan_spasi=True) for k in kolom}
    return IndeksRekap(tabel, kolom, opsi)


class TestNormalisasiHeader:
    def test_header_normal(self) -> None:
        assert _normalisasi_header(["Nama", "Kode"]) == ["Nama", "Kode"]

    def test_header_duplikat(self) -> None:
        hasil = _normalisasi_header(["Nama", "Nama", "Kode"])
        assert hasil[0] == "Nama"
        assert hasil[1] == "Nama_2"
        assert hasil[2] == "Kode"

    def test_header_kosong(self) -> None:
        hasil = _normalisasi_header(["Nama", "", "Kode"])
        assert hasil[1] == "Kolom_2"

    def test_header_spasi(self) -> None:
        hasil = _normalisasi_header(["Nama", "   ", "Kode"])
        assert hasil[1] == "Kolom_2"


class TestBacaExcel:
    def test_baca_excel_sederhana(self) -> None:
        """Buat file Excel dan baca."""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl tidak tersedia")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Nama", "Kode", "Nilai"])
        ws.append(["PT Maju", "K001", "100"])
        ws.append(["CV Berkah", "K002", "200"])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tes.xlsx"
            wb.save(str(path))

            tabel = baca_excel(path)
            assert len(tabel.baris) == 2
            assert "Nama" in tabel.kolom
            assert tabel.baris[0].data["Nama"] == "PT Maju"
            assert tabel.baris[0].data["Kode"] == "K001"

    def test_nol_di_depan_dipertahankan(self) -> None:
        """Nilai seperti '007' harus tetap '007', bukan 7."""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl tidak tersedia")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Kode"])
        ws.append(["007"])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tes.xlsx"
            wb.save(str(path))

            tabel = baca_excel(path)
            assert tabel.baris[0].data["Kode"] == "007"

    def test_file_tidak_ditemukan(self) -> None:
        with pytest.raises(FileNotFoundError):
            baca_excel(Path("/tidak/ada/file.xlsx"))

    def test_baris_header_kustom(self) -> None:
        """Baris header selain baris pertama."""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl tidak tersedia")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Judul Laporan"])  # Baris 1 - bukan header
        ws.append(["Nama", "Kode"])   # Baris 2 - header
        ws.append(["Maju", "K001"])   # Baris 3 - data

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tes.xlsx"
            wb.save(str(path))

            tabel = baca_excel(path, baris_header=2)
            assert "Nama" in tabel.kolom
            assert len(tabel.baris) == 1


class TestIndeksRekap:
    def test_cari_persis(self) -> None:
        baris_list = [
            _buat_baris("b1", {"kunci": "nilai_a"}),
            _buat_baris("b2", {"kunci": "nilai_b"}),
        ]
        indeks = _buat_indeks(baris_list, ["kunci"])
        # Cari dengan nilai ternormalisasi
        hasil = indeks.cari_persis("kunci", "Nilai_A".lower().replace(" ", ""))
        assert "b1" in hasil

    def test_cari_tidak_ada(self) -> None:
        baris_list = [_buat_baris("b1", {"kunci": "ada"})]
        indeks = _buat_indeks(baris_list, ["kunci"])
        hasil = indeks.cari_persis("kunci", "tidak_ada")
        assert len(hasil) == 0

    def test_cari_mengandung(self) -> None:
        baris_list = [
            _buat_baris("b1", {"nama": "maju jaya sejahtera"}),
            _buat_baris("b2", {"nama": "berkah abadi"}),
        ]
        indeks = _buat_indeks(baris_list, ["nama"])
        hasil = indeks.cari_mengandung("nama", "majujaya")
        assert "b1" in hasil

    def test_statistik_kolom(self) -> None:
        baris_list = [
            _buat_baris("b1", {"kunci": "a"}),
            _buat_baris("b2", {"kunci": "a"}),  # Duplikat
            _buat_baris("b3", {"kunci": ""}),   # Kosong
            _buat_baris("b4", {"kunci": "b"}),
        ]
        indeks = _buat_indeks(baris_list, ["kunci"])
        stat = indeks.statistik_kolom("kunci")
        assert stat["total_baris"] == 4
        assert stat["kosong"] == 1
        assert stat["duplikat"] >= 1

    def test_cari_kolom_tidak_ada(self) -> None:
        """Kolom yang tidak ada tidak menyebabkan crash."""
        baris_list = [_buat_baris("b1", {"ada": "nilai"})]
        indeks = _buat_indeks(baris_list, ["ada", "tidak_ada"])
        hasil = indeks.cari_persis("tidak_ada", "apapun")
        assert len(hasil) == 0


class TestGabungTabel:
    def test_gabung_dua_tabel(self) -> None:
        t1 = _buat_tabel([_buat_baris("b1", {"k": "v1"})])
        t2 = _buat_tabel([_buat_baris("b2", {"k": "v2"})])
        gabungan = gabung_tabel([t1, t2])
        assert len(gabungan.baris) == 2

    def test_gabung_kolom_berbeda(self) -> None:
        t1 = _buat_tabel([_buat_baris("b1", {"k1": "v1"})])
        t2 = _buat_tabel([_buat_baris("b2", {"k2": "v2"})])
        gabungan = gabung_tabel([t1, t2])
        assert "k1" in gabungan.kolom
        assert "k2" in gabungan.kolom
        # Baris b1 harus punya k2 dengan nilai kosong
        assert gabungan.baris[0].data.get("k2", "") == ""

    def test_gabung_kosong_raise(self) -> None:
        with pytest.raises(ValueError):
            gabung_tabel([])
