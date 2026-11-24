"""
services/profile_service.py - Layanan manajemen profil validasi.

Menyimpan, memuat, menduplikasi, menghapus, mengekspor, dan mengimpor profil.
Mendeteksi kolom yang hilang saat rekapan baru dimuat.
"""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from validator_dokumen.core.models import ProfilValidasi
from validator_dokumen.core.profile_schema import (
    muat_profil,
    profil_contoh,
    simpan_profil,
)
from validator_dokumen.utils.logger import log
from validator_dokumen.utils.paths import folder_profil


class ProfileService:
    """
    Layanan profil: CRUD profil validasi dari folder profiles/.
    Tidak ada logika bisnis validasi di sini.
    """

    def __init__(self, folder: Path | None = None) -> None:
        self._folder = folder or folder_profil()
        self._folder.mkdir(parents=True, exist_ok=True)

    def daftar_profil(self) -> list[tuple[str, str, Path]]:
        """
        Daftar semua profil yang tersedia.

        Returns:
            List (id, nama, path) diurutkan nama.
        """
        hasil: list[tuple[str, str, Path]] = []
        for path in sorted(self._folder.glob("*.json")):
            try:
                profil = muat_profil(path)
                hasil.append((profil.id, profil.nama, path))
            except Exception as e:
                log.warning("Tidak bisa memuat profil %s: %s", path, e)
        return hasil

    def muat(self, path: Path) -> ProfilValidasi:
        """
        Muat profil dari file. Validasi otomatis.

        Raises:
            FileNotFoundError, ProfilTidakValid
        """
        return muat_profil(path)

    def simpan(self, profil: ProfilValidasi, path: Path | None = None) -> Path:
        """
        Simpan profil. Jika path None, simpan ke folder profil dengan nama unik.

        Returns:
            Path file yang disimpan.
        """
        if path is None:
            # Buat nama file dari nama profil
            nama_bersih = "".join(c for c in profil.nama if c.isalnum() or c in " _-")[:40]
            nama_bersih = nama_bersih.strip().replace(" ", "_") or "profil"
            path = self._folder / f"{nama_bersih}.json"

        # Update timestamp
        profil_diperbarui = ProfilValidasi(
            schema_version=profil.schema_version,
            id=profil.id,
            nama=profil.nama,
            deskripsi=profil.deskripsi,
            field_dokumen=profil.field_dokumen,
            skema_pencocokan=profil.skema_pencocokan,
            aturan_field=profil.aturan_field,
            kondisi_jika_maka=profil.kondisi_jika_maka,
            pengaturan_ocr=profil.pengaturan_ocr,
            dibuat_pada=profil.dibuat_pada or datetime.now(UTC).isoformat(),
            diubah_pada=datetime.now(UTC).isoformat(),
        )

        simpan_profil(profil_diperbarui, path)
        log.info("Profil disimpan ke %s", path)
        return path

    def duplikasi(self, path_sumber: Path) -> Path:
        """
        Duplikasi profil dengan ID dan nama baru (+ " - Salinan").

        Returns:
            Path profil duplikat.
        """
        profil = muat_profil(path_sumber)
        nama_baru = f"{profil.nama} - Salinan"
        nama_bersih = "".join(c for c in nama_baru if c.isalnum() or c in " _-")[:40]
        nama_bersih = nama_bersih.strip().replace(" ", "_")
        path_baru = self._folder / f"{nama_bersih}.json"

        # Buat profil baru dengan ID baru
        profil_baru = ProfilValidasi(
            schema_version=profil.schema_version,
            id=str(uuid.uuid4()),
            nama=nama_baru,
            deskripsi=profil.deskripsi,
            field_dokumen=profil.field_dokumen,
            skema_pencocokan=profil.skema_pencocokan,
            aturan_field=profil.aturan_field,
            kondisi_jika_maka=profil.kondisi_jika_maka,
            pengaturan_ocr=profil.pengaturan_ocr,
            dibuat_pada=datetime.now(UTC).isoformat(),
            diubah_pada=datetime.now(UTC).isoformat(),
        )
        return self.simpan(profil_baru, path_baru)

    def hapus(self, path: Path) -> None:
        """Hapus profil dari disk."""
        if path.exists():
            path.unlink()
            log.info("Profil dihapus: %s", path)

    def ekspor(self, path_sumber: Path, path_tujuan: Path) -> None:
        """Ekspor profil ke lokasi lain."""
        shutil.copy2(str(path_sumber), str(path_tujuan))

    def impor(self, path_sumber: Path) -> Path:
        """
        Impor profil dari luar ke folder profil.

        Raises:
            ProfilTidakValid: Jika file bukan profil valid.
        """
        # Validasi dulu
        muat_profil(path_sumber)
        path_tujuan = self._folder / path_sumber.name

        # Hindari overwrite
        if path_tujuan.exists():
            stem = path_tujuan.stem
            suffix = path_tujuan.suffix
            counter = 1
            while path_tujuan.exists():
                path_tujuan = self._folder / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.copy2(str(path_sumber), str(path_tujuan))
        return path_tujuan

    def simpan_profil(self, profil: ProfilValidasi) -> Path:
        """Alias untuk menyimpan objek ProfilValidasi."""
        return self.simpan(profil)

    def dapatkan_profil(self, profil_id: str) -> ProfilValidasi | None:
        """Dapatkan profil berdasarkan ID atau nama file."""
        for _pid, _nama, path in self.daftar_profil():
            if _pid == profil_id:
                try:
                    return self.muat(path)
                except Exception:
                    return None
        # Coba muat langsung berdasarkan nama file
        p_path = self._folder / f"{profil_id}.json"
        if p_path.is_file():
            try:
                return self.muat(p_path)
            except Exception:
                return None
        return None

    def ekspor_profil(self, profil_id: str, path_tujuan: Path) -> None:
        """Ekspor profil ke lokasi tujuan."""
        for _pid, _nama, path in self.daftar_profil():
            if _pid == profil_id:
                self.ekspor(path, path_tujuan)
                return
        p_path = self._folder / f"{profil_id}.json"
        if p_path.is_file():
            self.ekspor(p_path, path_tujuan)
            return
        raise FileNotFoundError(f"Profil dengan ID '{profil_id}' tidak ditemukan.")

    def deteksi_kolom_hilang(
        self,
        profil: ProfilValidasi,
        kolom_rekap_tersedia: list[str],
    ) -> list[dict[str, Any]]:
        """
        Deteksi pasangan yang kolomnya hilang di rekapan baru.

        Returns:
            Daftar {skema_nama, pasangan_id, kolom_rekap, field_dokumen}
            untuk pasangan yang kolomnya tidak ada di rekapan.
        """
        hilang: list[dict[str, Any]] = []
        for skema in profil.skema_pencocokan:
            for pasangan in skema.pasangan:
                if pasangan.kolom_rekap not in kolom_rekap_tersedia:
                    hilang.append(
                        {
                            "skema_nama": skema.nama,
                            "pasangan_id": pasangan.id,
                            "kolom_rekap": pasangan.kolom_rekap,
                            "field_dokumen": pasangan.field_dokumen,
                        }
                    )
        return hilang

    def buat_profil_contoh(self) -> Path:
        """Buat dan simpan profil contoh ke folder profil."""
        profil = profil_contoh()
        path = self._folder / "profil_contoh_izin_usaha.json"
        return self.simpan(profil, path)
