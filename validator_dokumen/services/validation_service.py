"""
services/validation_service.py - Layanan orkestrasi validasi utama.

Menggabungkan pembacaan PDF, ekstraksi field, pencocokan, aturan,
dan penulisan output. Mendukung single file dan bulk folder.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from validator_dokumen.core.constants import APP_VERSION, PARALLEL_WORKERS_DEFAULT
from validator_dokumen.core.field_extractor import ekstrak_semua_field
from validator_dokumen.core.matcher import cocokkan_dokumen
from validator_dokumen.core.models import (
    HasilBulk,
    HasilValidasiDokumen,
    ProfilValidasi,
    StatusValidasi,
    TabelRekap,
)
from validator_dokumen.core.output_writer import _nama_folder_output, tulis_output_bulk
from validator_dokumen.core.pdf_reader import baca_pdf
from validator_dokumen.core.profile_schema import hash_profil
from validator_dokumen.core.recap_table import IndeksRekap
from validator_dokumen.core.rule_engine import (
    evaluasi_kondisi_jika_maka,
    evaluasi_semua_aturan_field,
)
from validator_dokumen.utils.logger import log


def _validasi_satu_dokumen(
    path_pdf: Path,
    profil: ProfilValidasi,
    indeks: IndeksRekap,
    callback_batal: Callable[[], bool] | None = None,
) -> HasilValidasiDokumen:
    """
    Validasi satu file PDF. Fungsi ini bisa dipanggil di proses terpisah.

    Args:
        path_pdf: Path ke file PDF.
        profil: Profil validasi aktif.
        indeks: Indeks rekapan yang sudah dibangun.
        callback_batal: Callable yang mengembalikan True jika proses harus berhenti.

    Returns:
        HasilValidasiDokumen lengkap.
    """
    waktu_mulai = time.time()

    try:
        # Langkah 1: Baca PDF
        pengaturan_ocr = dict(profil.pengaturan_ocr)
        hasil_baca = baca_pdf(
            path_pdf,
            paksa_ocr=pengaturan_ocr.get("paksa_ocr", False),
            pengaturan_ocr=pengaturan_ocr,
            callback_batal=callback_batal,
        )

        if not hasil_baca["bisa_dibaca"]:
            return HasilValidasiDokumen(
                nama_file=path_pdf.name,
                path_file=str(path_pdf),
                status=StatusValidasi.TIDAK_BISA_DIBACA,
                skema_terpakai=None,
                waktu_proses_detik=time.time() - waktu_mulai,
                error_teknis=hasil_baca["error"],
            )

        # Langkah 2: Ekstrak field
        hasil_field = ekstrak_semua_field(
            list(profil.field_dokumen),
            hasil_baca,
        )

        # Langkah 3: Cocokkan dengan rekapan
        semua_hasil_skema = cocokkan_dokumen(
            hasil_field,
            profil.skema_pencocokan,
            indeks,
        )

        # Tentukan skema terbaik yang berhasil
        skema_terbaik = None
        for hs in semua_hasil_skema:
            if hs.status in (StatusValidasi.VALID, StatusValidasi.PERLU_DICEK):
                skema_terbaik = hs
                break

        if skema_terbaik is None and semua_hasil_skema:
            skema_terbaik = semua_hasil_skema[-1]

        # Langkah 4: Evaluasi aturan field
        masalah: list[str] = []
        jejak: list[Any] = []

        if profil.aturan_field:
            baris_rekap = None
            if skema_terbaik and skema_terbaik.baris_rekap_id:
                baris_rekap = indeks.dapatkan_baris(skema_terbaik.baris_rekap_id)

            hasil_aturan = evaluasi_semua_aturan_field(
                list(profil.aturan_field),
                hasil_field,
                baris_rekap,
            )
            for lolos, pesan, j in hasil_aturan:
                if not lolos and pesan:
                    masalah.append(pesan)
                jejak.append(j)

        # Langkah 5: Evaluasi kondisional JIKA-MAKA
        if profil.kondisi_jika_maka and skema_terbaik:
            baris_rekap = indeks.dapatkan_baris(skema_terbaik.baris_rekap_id or "")
            hp_list = list(skema_terbaik.pasangan_hasil)

            hasil_kondisi = evaluasi_kondisi_jika_maka(
                list(profil.kondisi_jika_maka),
                hasil_field,
                baris_rekap,
                hp_list,
            )
            for terpicu, _aksi, pesan, j in hasil_kondisi:
                if terpicu and pesan:
                    masalah.append(pesan)
                jejak.append(j)

        # Tentukan status akhir
        status_akhir = skema_terbaik.status if skema_terbaik else StatusValidasi.TIDAK_VALID

        # Aturan gagal -> paksa TIDAK_VALID
        if masalah and status_akhir == StatusValidasi.VALID:
            status_akhir = StatusValidasi.TIDAK_VALID

        # Tambah masalah dari skema
        if skema_terbaik and skema_terbaik.alasan and status_akhir != StatusValidasi.VALID:
            masalah.insert(0, skema_terbaik.alasan)

        return HasilValidasiDokumen(
            nama_file=path_pdf.name,
            path_file=str(path_pdf),
            status=status_akhir,
            skema_terpakai=skema_terbaik.skema_nama if skema_terbaik else None,
            skor=skema_terbaik.skor if skema_terbaik else 0,
            skor_total=skema_terbaik.skor_total
            if skema_terbaik
            else len(profil.skema_pencocokan[0].pasangan)
            if profil.skema_pencocokan
            else 0,
            baris_rekap_nomor=skema_terbaik.baris_rekap_nomor if skema_terbaik else None,
            file_rekap=skema_terbaik.file_rekap if skema_terbaik else "",
            sheet_rekap=skema_terbaik.sheet_rekap if skema_terbaik else "",
            hasil_field=hasil_field,
            hasil_skema=semua_hasil_skema,
            masalah=tuple(masalah),
            jejak_keputusan=tuple(jejak),
            waktu_proses_detik=time.time() - waktu_mulai,
        )

    except Exception as e:
        log.exception("Error validasi %s: %s", path_pdf, e)
        return HasilValidasiDokumen(
            nama_file=path_pdf.name,
            path_file=str(path_pdf),
            status=StatusValidasi.TIDAK_BISA_DIBACA,
            skema_terpakai=None,
            waktu_proses_detik=time.time() - waktu_mulai,
            error_teknis=f"Error tidak terduga: {type(e).__name__}: {e}",
        )


class ValidationService:
    """
    Layanan validasi utama: single file dan bulk folder.
    UI memanggil ini melalui workers/; tidak ada logika bisnis di UI.
    """

    def __init__(self) -> None:
        self._batal = False

    def batal(self) -> None:
        """Set flag batal untuk menghentikan proses bulk."""
        self._batal = True

    def _cek_batal(self) -> bool:
        return self._batal

    def validasi_satu(
        self,
        path_pdf: Path,
        profil: ProfilValidasi,
        indeks: IndeksRekap,
    ) -> HasilValidasiDokumen:
        """
        Validasi satu file PDF.

        Args:
            path_pdf: Path file PDF.
            profil: Profil validasi.
            indeks: Indeks rekapan.

        Returns:
            HasilValidasiDokumen.
        """
        self._batal = False
        return _validasi_satu_dokumen(path_pdf, profil, indeks, self._cek_batal)

    def validasi_satu_file(
        self,
        path_dokumen: Path | str,
        profil: ProfilValidasi,
        tabel_rekap: TabelRekap,
    ) -> HasilValidasiDokumen:
        """Helper untuk memvalidasi satu file dokumen langsung dari TabelRekap."""
        kolom_kunci: list[str] = []
        opsi_norm: dict[str, Any] = {}
        for skema in profil.skema_pencocokan:
            for p in skema.pasangan:
                if p.kolom_rekap not in kolom_kunci:
                    kolom_kunci.append(p.kolom_rekap)
                    opsi_norm[p.kolom_rekap] = p.normalisasi

        indeks = IndeksRekap(tabel_rekap, kolom_kunci, opsi_norm)
        return self.validasi_satu(Path(path_dokumen), profil, indeks)

    def validasi_bulk(
        self,
        folder_pdf: Path,
        profil: ProfilValidasi,
        indeks: IndeksRekap,
        tabel_rekap: TabelRekap,
        sertakan_subfolder: bool = False,
        callback_progres: Callable[[int, int, HasilValidasiDokumen], None] | None = None,
        jumlah_proses: int = PARALLEL_WORKERS_DEFAULT,
        folder_output: Path | None = None,
        pindah_file: bool = False,
    ) -> HasilBulk:
        """
        Validasi semua PDF dalam folder secara paralel.

        Args:
            folder_pdf: Folder sumber PDF.
            profil: Profil validasi.
            indeks: Indeks rekapan.
            tabel_rekap: Tabel rekapan (untuk laporan tidak terpakai).
            sertakan_subfolder: Jika True, cari PDF rekursif.
            callback_progres: Dipanggil setiap file selesai (selesai, total, hasil).
            jumlah_proses: Jumlah proses paralel (-1 = otomatis).
            folder_output: Path folder output (None = di samping folder_pdf).
            pindah_file: Jika True, pindah file (default: salin).

        Returns:
            HasilBulk lengkap.
        """
        import os

        self._batal = False
        waktu_mulai = datetime.now(UTC)

        # Kumpulkan file PDF
        pola = "**/*.pdf" if sertakan_subfolder else "*.pdf"
        file_pdf = sorted(folder_pdf.glob(pola))

        if not file_pdf:
            raise ValueError(f"Tidak ada file PDF di folder: {folder_pdf}")

        total = len(file_pdf)
        log.info("Validasi bulk: %d file PDF", total)

        # Tentukan jumlah proses
        if jumlah_proses <= 0:
            jumlah_proses = max(1, (os.cpu_count() or 2) - 1)

        # Tentukan folder output
        nama_folder = _nama_folder_output(waktu_mulai)
        if folder_output is None:
            folder_output_path = folder_pdf.parent / nama_folder
        else:
            folder_output_path = folder_output / nama_folder

        # Checkpoint: muat hasil sebelumnya jika ada
        hasil_dict: dict[str, HasilValidasiDokumen] = {}
        folder_output_path / "_checkpoint.json"

        # Proses file (sequential untuk kemudahan debugging di tahap 1)
        # Di tahap berikutnya bisa pakai ProcessPoolExecutor
        selesai = 0
        for path_pdf in file_pdf:
            if self._batal:
                log.info("Validasi bulk dibatalkan setelah %d/%d file", selesai, total)
                break

            if path_pdf.name in hasil_dict:
                selesai += 1
                if callback_progres:
                    callback_progres(selesai, total, hasil_dict[path_pdf.name])
                continue

            hasil = _validasi_satu_dokumen(path_pdf, profil, indeks, self._cek_batal)
            hasil_dict[path_pdf.name] = hasil
            selesai += 1

            if callback_progres:
                callback_progres(selesai, total, hasil)

        # Susun hasil bulk
        semua_hasil = tuple(hasil_dict[p.name] for p in file_pdf if p.name in hasil_dict)
        waktu_selesai = datetime.now(UTC)

        def hitung_status(status: StatusValidasi) -> int:
            return sum(1 for h in semua_hasil if h.status == status)

        hasil_bulk = HasilBulk(
            hasil_per_file=semua_hasil,
            folder_output=nama_folder,
            total=len(semua_hasil),
            valid=hitung_status(StatusValidasi.VALID),
            tidak_valid=hitung_status(StatusValidasi.TIDAK_VALID),
            perlu_dicek=hitung_status(StatusValidasi.PERLU_DICEK),
            tidak_bisa_dibaca=hitung_status(StatusValidasi.TIDAK_BISA_DIBACA),
            waktu_mulai=waktu_mulai.isoformat(),
            waktu_selesai=waktu_selesai.isoformat(),
            versi_app=APP_VERSION,
            nama_profil=profil.nama,
            hash_profil=hash_profil(profil),
            hash_rekap=tabel_rekap.hash_file,
        )

        # Tulis output
        tulis_output_bulk(hasil_bulk, folder_pdf, tabel_rekap, pindah_file)
        log.info(
            "Bulk selesai: %d valid, %d tidak valid, %d perlu dicek, %d tidak terbaca",
            hasil_bulk.valid,
            hasil_bulk.tidak_valid,
            hasil_bulk.perlu_dicek,
            hasil_bulk.tidak_bisa_dibaca,
        )

        return hasil_bulk
