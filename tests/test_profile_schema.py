"""
tests/test_profile_schema.py - Tes unit untuk serialisasi dan validasi profil.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

import pytest

from validator_dokumen.core.models import (
    JikaAdaTidakCocok,
    ModeCocok,
    OpsiNormalisasi,
    PasanganPencocokan,
    PeranPasangan,
    SkemaPencocokan,
    StatusValidasi,
)
from validator_dokumen.core.profile_schema import (
    ProfilTidakValid,
    dict_ke_profil,
    hash_profil,
    muat_profil,
    profil_contoh,
    profil_ke_dict,
    simpan_profil,
)


class TestSerialisasiProfil:
    def test_profil_contoh_valid(self) -> None:
        """Profil contoh harus bisa dibuat tanpa error."""
        profil = profil_contoh()
        assert profil.nama != ""
        assert len(profil.skema_pencocokan) > 0
        assert len(profil.field_dokumen) > 0

    def test_round_trip(self) -> None:
        """Profil yang diserialisasi dan di-deserialisasi harus sama."""
        profil = profil_contoh()
        d = profil_ke_dict(profil)
        profil2 = dict_ke_profil(d)

        assert profil.nama == profil2.nama
        assert profil.id == profil2.id
        assert len(profil.skema_pencocokan) == len(profil2.skema_pencocokan)
        assert len(profil.field_dokumen) == len(profil2.field_dokumen)

    def test_simpan_dan_muat(self) -> None:
        """Profil yang disimpan ke file harus bisa dimuat kembali."""
        profil = profil_contoh()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_profil.json"
            simpan_profil(profil, path)
            assert path.exists()
            profil2 = muat_profil(path)
            assert profil2.nama == profil.nama

    def test_hash_profil_deterministik(self) -> None:
        """Hash profil harus sama untuk profil yang sama."""
        profil = profil_contoh()
        hash1 = hash_profil(profil)
        hash2 = hash_profil(profil)
        assert hash1 == hash2

    def test_hash_berbeda_jika_profil_beda(self) -> None:
        """Hash profil harus berbeda untuk profil yang berbeda."""
        import dataclasses
        profil1 = profil_contoh()
        # Buat profil dengan nama berbeda
        profil2 = dataclasses.replace(profil1, nama="Nama Berbeda", id=str(uuid.uuid4()))
        assert hash_profil(profil1) != hash_profil(profil2)


class TestValidasiProfil:
    def test_profil_tidak_valid_bukan_dict(self) -> None:
        with pytest.raises(ProfilTidakValid):
            dict_ke_profil([])  # type: ignore[arg-type]

    def test_profil_k_melebihi_pasangan(self) -> None:
        """K yang melebihi jumlah pasangan harus raise ProfilTidakValid."""
        d = profil_ke_dict(profil_contoh())
        d["skema_pencocokan"][0]["k_minimum"] = 999  # Terlalu besar
        with pytest.raises(ProfilTidakValid, match="k_minimum"):
            dict_ke_profil(d)

    def test_profil_mode_tidak_valid(self) -> None:
        """Mode pencocokan yang tidak dikenal harus raise ProfilTidakValid."""
        d = profil_ke_dict(profil_contoh())
        d["skema_pencocokan"][0]["pasangan"][0]["mode"] = "ModeYangTidakAda"
        with pytest.raises(ProfilTidakValid):
            dict_ke_profil(d)

    def test_file_tidak_ditemukan(self) -> None:
        with pytest.raises(FileNotFoundError):
            muat_profil(Path("/tidak/ada/file.json"))

    def test_json_tidak_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rusak.json"
            path.write_text("ini bukan json valid {{{", encoding="utf-8")
            with pytest.raises(ProfilTidakValid, match="JSON"):
                muat_profil(path)

    def test_peran_tidak_valid(self) -> None:
        d = profil_ke_dict(profil_contoh())
        d["skema_pencocokan"][0]["pasangan"][0]["peran"] = "PeranTidakAda"
        with pytest.raises(ProfilTidakValid):
            dict_ke_profil(d)

    def test_aksi_kondisional_tidak_valid(self) -> None:
        d = profil_ke_dict(profil_contoh())
        d["kondisi_jika_maka"] = [{
            "id": str(uuid.uuid4()),
            "kondisi": [],
            "aksi": "aksi_tidak_ada",
            "parameter_aksi": {},
            "aktif": True,
            "pesan_kustom": "",
        }]
        with pytest.raises(ProfilTidakValid):
            dict_ke_profil(d)

    def test_simpan_atomik(self) -> None:
        """Penulisan profil harus atomik (tidak ada .tmp yang tertinggal)."""
        profil = profil_contoh()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            simpan_profil(profil, path)
            # Tidak boleh ada file .tmp yang tertinggal
            assert not path.with_suffix(".tmp").exists()
            assert path.exists()
