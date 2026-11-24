"""
services/recap_service.py - Layanan pengelolaan tabel rekapan.

Memuat, menggabungkan, membangun indeks, dan memberikan statistik rekapan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from validator_dokumen.core.models import OpsiNormalisasi, TabelRekap
from validator_dokumen.core.recap_table import IndeksRekap, baca_excel, gabung_tabel
from validator_dokumen.utils.logger import log


class RecapService:
    """
    Layanan rekapan: muat, gabung, indeks, statistik.
    Indeks dibangun sekali dan dipakai ulang untuk semua dokumen.
    """

    def __init__(self) -> None:
        self._tabel: TabelRekap | None = None
        self._indeks: IndeksRekap | None = None

    def muat_excel(
        self,
        path: Path,
        sheet_nama: str | None = None,
        baris_header: int = 1,
    ) -> TabelRekap:
        """
        Muat satu file Excel sebagai tabel rekapan.

        Raises:
            FileNotFoundError, ValueError
        """
        tabel = baca_excel(path, sheet_nama, baris_header)
        self._tabel = tabel
        self._indeks = None  # Reset indeks
        log.info("Rekapan dimuat: %s baris dari %s", len(tabel.baris), path)
        return tabel

    def muat_tabel_rekap(
        self,
        path: Path,
        sheet_nama: str | None = None,
        baris_header: int = 1,
        sheet_name: str | None = None,
    ) -> TabelRekap:
        """Alias serbaguna untuk memuat tabel rekapan acuan."""
        sh = sheet_nama or sheet_name
        return self.muat_excel(path, sheet_nama=sh, baris_header=baris_header)

    def muat_beberapa(self, file_sheet_list: list[tuple[Path, str | None, int]]) -> TabelRekap:
        """
        Muat beberapa file/sheet Excel dan gabungkan.

        Args:
            file_sheet_list: List (path, sheet_nama, baris_header)
        """
        tabel_list: list[TabelRekap] = []
        for path, sheet, header in file_sheet_list:
            try:
                tabel = baca_excel(path, sheet, header)
                tabel_list.append(tabel)
                log.info("Dimuat %d baris dari %s/%s", len(tabel.baris), path, sheet or "default")
            except Exception as e:
                log.error("Gagal memuat %s: %s", path, e)

        if not tabel_list:
            raise ValueError("Tidak ada file rekapan yang berhasil dimuat.")

        tabel_gabung = gabung_tabel(tabel_list)
        self._tabel = tabel_gabung
        self._indeks = None
        return tabel_gabung

    def bangun_indeks(
        self,
        kolom_diindeks: list[str],
        opsi_normalisasi: dict[str, OpsiNormalisasi] | None = None,
    ) -> IndeksRekap:
        """
        Bangun indeks terbalik dari tabel rekapan yang sudah dimuat.

        Args:
            kolom_diindeks: Kolom yang perlu diindeks.
            opsi_normalisasi: Opsi per kolom; None = gunakan default.

        Returns:
            IndeksRekap yang siap dipakai.

        Raises:
            RuntimeError: Jika tabel belum dimuat.
        """
        if self._tabel is None:
            raise RuntimeError("Rekapan belum dimuat. Panggil muat_excel() dulu.")

        if opsi_normalisasi is None:
            opsi_normalisasi = {}

        # Pastikan semua kolom punya opsi (pakai default jika tidak ada)
        for kolom in kolom_diindeks:
            if kolom not in opsi_normalisasi:
                opsi_normalisasi[kolom] = OpsiNormalisasi()

        self._indeks = IndeksRekap(self._tabel, kolom_diindeks, opsi_normalisasi)
        log.info(
            "Indeks dibangun untuk %d kolom, %d baris", len(kolom_diindeks), len(self._tabel.baris)
        )
        return self._indeks

    def dapatkan_indeks(self) -> IndeksRekap:
        """
        Dapatkan indeks yang sudah dibangun.

        Raises:
            RuntimeError: Jika indeks belum dibangun.
        """
        if self._indeks is None:
            raise RuntimeError("Indeks belum dibangun. Panggil bangun_indeks() dulu.")
        return self._indeks

    @property
    def tabel(self) -> TabelRekap | None:
        """Tabel rekapan saat ini."""
        return self._tabel

    def statistik(self) -> dict[str, Any]:
        """Statistik tabel rekapan."""
        if self._tabel is None:
            return {"status": "belum dimuat"}

        return {
            "total_baris": len(self._tabel.baris),
            "jumlah_kolom": len(self._tabel.kolom),
            "kolom": list(self._tabel.kolom),
            "sumber_file": self._tabel.sumber_file,
            "hash_file": self._tabel.hash_file,
        }

    def statistik_kolom(self, kolom: str) -> dict[str, Any]:
        """Statistik kekuatan kunci untuk satu kolom."""
        if self._indeks is None:
            if self._tabel is None:
                return {}
            # Hitung manual tanpa indeks
            nilai_semua = [b.data.get(kolom, "") for b in self._tabel.baris]
            kosong = sum(1 for v in nilai_semua if not v.strip())
            unik = len({v for v in nilai_semua if v.strip()})
            return {
                "total_baris": len(self._tabel.baris),
                "unik": unik,
                "kosong": kosong,
                "duplikat": len(nilai_semua) - kosong - unik,
            }
        return self._indeks.statistik_kolom(kolom)
