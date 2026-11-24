"""
tests/test_output_writer.py - Tes unit untuk output_writer.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from validator_dokumen.core.models import (
    HasilBulk,
    HasilValidasiDokumen,
    StatusValidasi,
    TabelRekap,
    BarisRekap,
)
from validator_dokumen.core.output_writer import (
    _tulis_catatan_txt,
    _tulis_rekap_tidak_terpakai,
    tulis_output_bulk,
)
from validator_dokumen.core.constants import OUTPUT_ENCODING


def _buat_hasil(
    nama: str,
    path: str,
    status: StatusValidasi,
    masalah: tuple[str, ...] = (),
) -> HasilValidasiDokumen:
    return HasilValidasiDokumen(
        nama_file=nama,
        path_file=path,
        status=status,
        skema_terpakai="Skema Tes",
        skor=5,
        skor_total=8,
        masalah=masalah,
    )


def _buat_bulk(
    hasil_per_file: tuple[HasilValidasiDokumen, ...],
    folder_output: str = "hasil_tes",
) -> HasilBulk:
    return HasilBulk(
        hasil_per_file=hasil_per_file,
        folder_output=folder_output,
        total=len(hasil_per_file),
        valid=sum(1 for h in hasil_per_file if h.status == StatusValidasi.VALID),
        tidak_valid=sum(1 for h in hasil_per_file if h.status == StatusValidasi.TIDAK_VALID),
        perlu_dicek=sum(1 for h in hasil_per_file if h.status == StatusValidasi.PERLU_DICEK),
        tidak_bisa_dibaca=sum(1 for h in hasil_per_file if h.status == StatusValidasi.TIDAK_BISA_DIBACA),
        waktu_mulai=datetime.now(timezone.utc).isoformat(),
        waktu_selesai=datetime.now(timezone.utc).isoformat(),
        versi_app="1.0.0",
        nama_profil="Profil Tes",
        hash_profil="abc123",
        hash_rekap="def456",
    )


class TestStrukturFolder:
    def test_folder_valid_dan_not_valid_dibuat(self) -> None:
        """Folder valid/ dan not_valid/ harus selalu dibuat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder_pdf = Path(tmpdir) / "pdf"
            folder_pdf.mkdir()

            hasil = (_buat_hasil("test.pdf", str(folder_pdf / "test.pdf"), StatusValidasi.VALID),)
            bulk = _buat_bulk(hasil)

            tulis_output_bulk(bulk, folder_pdf)

            folder_out = folder_pdf.parent / "hasil_tes"
            assert (folder_out / "valid").exists()
            assert (folder_out / "not_valid").exists()

    def test_catatan_kesalahan_txt_tanpa_error(self) -> None:
        """Catatan kesalahan tetap dibuat walau tidak ada file gagal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _tulis_catatan_txt(folder, [])
            path = folder / "catatan_kesalahan.txt"
            assert path.exists()
            konten = path.read_text(encoding=OUTPUT_ENCODING)
            assert "Tidak ada kesalahan" in konten

    def test_catatan_kesalahan_txt_ber_bom(self) -> None:
        """File .txt harus UTF-8 dengan BOM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            hasil = [_buat_hasil("test.pdf", "/path/test.pdf", StatusValidasi.TIDAK_VALID,
                                  masalah=("Field tidak cocok",))]
            _tulis_catatan_txt(folder, hasil)
            path = folder / "catatan_kesalahan.txt"
            # BOM UTF-8 adalah b'\xef\xbb\xbf'
            raw = path.read_bytes()
            assert raw[:3] == b"\xef\xbb\xbf"

    def test_nama_bentrok_ditangani(self) -> None:
        """File dengan nama sama tidak boleh overwrite, harus beri akhiran _1, _2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            # Buat file yang sudah ada
            (folder / "test.pdf").write_bytes(b"original")

            from validator_dokumen.core.output_writer import _salin_atau_pindah_file
            import shutil

            sumber = folder / "sumber.pdf"
            sumber.write_bytes(b"salin")

            tujuan = folder / "test.pdf"
            _salin_atau_pindah_file(sumber, tujuan, pindah=False)

            # File asli tetap ada
            assert (folder / "test.pdf").read_bytes() == b"original"
            # File baru dengan akhiran _1
            assert (folder / "test_1.pdf").exists()


class TestRekapTidakTerpakai:
    def test_rekap_tidak_terpakai(self) -> None:
        """Baris yang tidak dipakai harus ada di laporan."""
        baris_terpakai = BarisRekap(
            id="b1", data={"kol": "v1"}, sumber_file="rekap.xlsx",
            sumber_sheet="Data", nomor_baris_asli=2,
        )
        baris_tidak_terpakai = BarisRekap(
            id="b2", data={"kol": "v2"}, sumber_file="rekap.xlsx",
            sumber_sheet="Data", nomor_baris_asli=3,
        )
        tabel = TabelRekap(
            baris=(baris_terpakai, baris_tidak_terpakai),
            kolom=("kol",),
            sumber_file="rekap.xlsx",
            hash_file="abc",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _tulis_rekap_tidak_terpakai(folder, tabel, {"b1"})
            path = folder / "rekapan_tidak_terpakai.xlsx"
            assert path.exists()
