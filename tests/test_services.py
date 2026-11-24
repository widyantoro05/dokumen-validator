"""
tests/test_services.py - Tes untuk ValidationService, ProfileService, RecapService, AuditLog.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from validator_dokumen.core.models import (
    OpsiNormalisasi,
    ProfilValidasi,
    StatusValidasi,
    TabelRekap,
)
from validator_dokumen.core.profile_schema import profil_contoh
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.core.audit_log import tulis_log_audit


class TestProfileService:
    def test_crud_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            ps = ProfileService(folder)
            
            # Buat contoh
            path_contoh = ps.buat_profil_contoh()
            assert path_contoh.exists()
            
            # Daftar
            daftar = ps.daftar_profil()
            assert len(daftar) == 1
            pid, nama, p_path = daftar[0]
            assert "Izin" in nama
            
            # Muat
            p = ps.muat(path_contoh)
            assert isinstance(p, ProfilValidasi)
            
            # Duplikasi
            path_duplikat = ps.duplikasi(path_contoh)
            assert path_duplikat.exists()
            assert len(ps.daftar_profil()) == 2
            
            # Hapus
            ps.hapus(path_duplikat)
            assert not path_duplikat.exists()
            assert len(ps.daftar_profil()) == 1

    def test_ekspor_impor_dan_kolom_hilang(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            ps = ProfileService(folder / "profiles")
            path_contoh = ps.buat_profil_contoh()
            p = ps.muat(path_contoh)
            
            # Ekspor
            path_ekspor = folder / "ekspor.json"
            ps.ekspor(path_contoh, path_ekspor)
            assert path_ekspor.exists()
            
            # Impor
            path_impor = ps.impor(path_ekspor)
            assert path_impor.exists()
            
            # Deteksi kolom hilang
            hilang = ps.deteksi_kolom_hilang(p, ["No Izin"])
            assert len(hilang) > 0


class TestRecapService:
    def test_muat_dan_indeks(self) -> None:
        path_rekap = Path("tests/data/rekapan.xlsx")
        if not path_rekap.exists():
            pytest.skip("Data rekapan belum ada")
            
        rs = RecapService()
        assert rs.statistik()["status"] == "belum dimuat"
        
        tabel = rs.muat_excel(path_rekap)
        assert len(tabel.baris) >= 200
        
        stat = rs.statistik()
        assert stat["total_baris"] >= 200
        
        # Bangun indeks
        indeks = rs.bangun_indeks(["No Izin", "Nama Perusahaan"])
        assert indeks is not None
        assert rs.dapatkan_indeks() is indeks
        
        stat_kol = rs.statistik_kolom("No Izin")
        assert stat_kol["total_baris"] >= 200

    def test_error_handling(self) -> None:
        rs = RecapService()
        with pytest.raises(RuntimeError):
            rs.bangun_indeks(["Kolom"])
        with pytest.raises(RuntimeError):
            rs.dapatkan_indeks()


class TestValidationService:
    def test_validasi_satu_file_dan_bulk(self) -> None:
        data_dir = Path("tests/data")
        rekap_path = data_dir / "rekapan.xlsx"
        pdf_benar = data_dir / "pdf_benar.pdf"
        
        if not rekap_path.exists() or not pdf_benar.exists():
            pytest.skip("File data contoh belum ada")
            
        ps = ProfileService()
        profil = profil_contoh()
        
        rs = RecapService()
        tabel = rs.muat_excel(rekap_path)
        indeks = rs.bangun_indeks(["No Izin", "NIB", "Nama Perusahaan", "Jenis Usaha", "Alamat", "Tanggal Terbit", "Tanggal Berakhir", "NPWP"])
        
        vs = ValidationService()
        hasil = vs.validasi_satu(pdf_benar, profil, indeks)
        assert hasil.status in (StatusValidasi.VALID, StatusValidasi.PERLU_DICEK)
        
        # Validasi PDF salah nomor
        pdf_salah = data_dir / "pdf_nomor_salah.pdf"
        if pdf_salah.exists():
            hasil_salah = vs.validasi_satu(pdf_salah, profil, indeks)
            assert hasil_salah.status in (StatusValidasi.TIDAK_VALID, StatusValidasi.PERLU_DICEK)
            
        # Validasi bulk
        with tempfile.TemporaryDirectory() as tmpdir:
            folder_out = Path(tmpdir)
            hasil_bulk = vs.validasi_bulk(
                folder_pdf=data_dir,
                profil=profil,
                indeks=indeks,
                tabel_rekap=tabel,
                folder_output=folder_out,
            )
            assert hasil_bulk.total > 0
            assert hasil_bulk.valid >= 1

    def test_recap_service_muat_beberapa(self) -> None:
        path_rekap = Path("tests/data/rekapan.xlsx")
        if not path_rekap.exists():
            pytest.skip("Data rekapan belum ada")
        rs = RecapService()
        tabel = rs.muat_beberapa([(path_rekap, "Data Izin", 1)])
        assert len(tabel.baris) >= 200

        with pytest.raises(ValueError, match="Tidak ada file rekapan yang berhasil dimuat"):
            rs.muat_beberapa([(Path("tidak_ada_file.xlsx"), None, 1)])

    def test_validasi_dengan_aturan_dan_kondisi(self) -> None:
        import uuid
        from validator_dokumen.core.models import (
            AksiKondisional,
            AturanField,
            KondisiJikaMaka,
            ProfilValidasi,
        )
        data_dir = Path("tests/data")
        rekap_path = data_dir / "rekapan.xlsx"
        pdf_benar = data_dir / "pdf_benar.pdf"

        ps = ProfileService()
        p_base = profil_contoh()
        
        # Tambahkan aturan field dan kondisi jika maka
        aturan = (
            AturanField(str(uuid.uuid4()), "nomor_izin", "wajib_ada", {}, True, "Nomor izin wajib!"),
            AturanField(str(uuid.uuid4()), "nib", "format_pola", {"pola": "nib"}, True),
        )
        kondisi = (
            KondisiJikaMaka(
                str(uuid.uuid4()),
                ({"sumber": "field", "nama": "nomor_izin", "operator": "tidak kosong", "nilai": ""},),
                AksiKondisional.WAJIB_ADA_FIELD,
                {"field_nama": "nomor_izin"},
                True,
            ),
        )
        profil = ProfilValidasi(
            schema_version=p_base.schema_version,
            id=str(uuid.uuid4()),
            nama="Profil Dengan Aturan",
            deskripsi="Tes",
            field_dokumen=p_base.field_dokumen,
            skema_pencocokan=p_base.skema_pencocokan,
            aturan_field=aturan,
            kondisi_jika_maka=kondisi,
            pengaturan_ocr=p_base.pengaturan_ocr,
        )

        rs = RecapService()
        rs.muat_excel(rekap_path)
        kolom = [pas.kolom_rekap for pas in profil.skema_pencocokan[0].pasangan]
        indeks = rs.bangun_indeks(kolom)

        vs = ValidationService()
        res = vs.validasi_satu(pdf_benar, profil, indeks)
        assert len(res.jejak_keputusan) > 0

        profil = profil_contoh()
        rs = RecapService()
        rekap_path = Path("tests/data/rekapan.xlsx")
        tabel = rs.muat_excel(rekap_path)
        indeks = rs.bangun_indeks(["No Izin"])

        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir)
            with pytest.raises(ValueError, match="Tidak ada file PDF"):
                vs.validasi_bulk(empty_dir, profil, indeks, tabel)


class TestAuditLog:
    def test_tulis_log_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            tulis_log_audit(
                folder_output=folder,
                nama_file="test.pdf",
                status_lama=StatusValidasi.TIDAK_VALID,
                status_baru=StatusValidasi.VALID,
                catatan="Izin sudah diverifikasi manual",
            )
            path_log = folder / "log_audit.txt"
            assert path_log.exists()
            teks = path_log.read_text(encoding="utf-8-sig")
            assert "test.pdf" in teks
            assert "Izin sudah diverifikasi manual" in teks
