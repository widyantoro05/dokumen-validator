"""
workers/validation_worker.py - QThread worker untuk eksekusi validasi tanpa memblokir thread UI.

Memancarkan sinyal:
- progress(current, total, file_name, eta_str)
- result_batch(list of HasilValidasiDokumen) dengan batching ~100ms
- finished(HasilBulk)
- error(error_message)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from validator_dokumen.core.models import (
    HasilValidasiDokumen,
    ProfilValidasi,
    TabelRekap,
)
from validator_dokumen.core.recap_table import IndeksRekap
from validator_dokumen.services.validation_service import ValidationService


class ValidationWorker(QThread):
    """
    Worker QThread untuk menjalankan proses validasi bulk atau single file.
    """

    progress = Signal(int, int, str, str)  # selesai, total, nama_file, estimasi_waktu
    result_batch = Signal(list)  # list[HasilValidasiDokumen] (batch update ~100ms)
    finished_bulk = Signal(object)  # HasilBulk
    finished_single = Signal(object)  # HasilValidasiDokumen
    error_occurred = Signal(str)  # Pesan error

    def __init__(
        self,
        validation_service: ValidationService,
        profil: ProfilValidasi,
        indeks: IndeksRekap,
        tabel_rekap: TabelRekap,
        input_path: Path,
        is_bulk: bool = True,
        sertakan_subfolder: bool = False,
        pindah_file: bool = False,
        folder_output: Path | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._vs = validation_service
        self._profil = profil
        self._indeks = indeks
        self._tabel_rekap = tabel_rekap
        self._input_path = input_path
        self._is_bulk = is_bulk
        self._subfolder = sertakan_subfolder
        self._pindah_file = pindah_file
        self._folder_output = folder_output

        self._pending_results: list[HasilValidasiDokumen] = []
        self._last_batch_time: float = 0.0
        self._start_time: float = 0.0

    def cancel(self) -> None:
        """Batalkan proses validasi."""
        self._vs.batal()

    def run(self) -> None:
        try:
            if not self._is_bulk:
                # Validasi single file
                res = self._vs.validasi_satu(self._input_path, self._profil, self._indeks)
                self.finished_single.emit(res)
                return

            # Validasi bulk folder
            self._start_time = time.time()
            self._last_batch_time = time.time()
            self._pending_results.clear()

            def progress_cb(current: int, total: int, doc_res: HasilValidasiDokumen) -> None:
                self._pending_results.append(doc_res)
                now = time.time()

                # Hitung ETA
                elapsed = now - self._start_time
                if current > 0 and current < total:
                    rate = elapsed / current
                    remaining_secs = int(rate * (total - current))
                    mins, secs = divmod(remaining_secs, 60)
                    eta_str = f"~{mins:02d}:{secs:02d} tersisa"
                elif current >= total:
                    eta_str = "Selesai"
                else:
                    eta_str = "Menghitung..."

                # Batching ~100ms untuk pembaruan UI yang halus
                if (now - self._last_batch_time >= 0.1) or (current >= total):
                    self.result_batch.emit(list(self._pending_results))
                    self._pending_results.clear()
                    self._last_batch_time = now

                self.progress.emit(current, total, doc_res.nama_file, eta_str)

            bulk_res = self._vs.validasi_bulk(
                folder_pdf=self._input_path,
                profil=self._profil,
                indeks=self._indeks,
                tabel_rekap=self._tabel_rekap,
                sertakan_subfolder=self._subfolder,
                callback_progres=progress_cb,
                folder_output=self._folder_output,
                pindah_file=self._pindah_file,
            )

            # Kirim sisa batch jika ada
            if self._pending_results:
                self.result_batch.emit(list(self._pending_results))
                self._pending_results.clear()

            self.finished_bulk.emit(bulk_res)

        except Exception as e:
            self.error_occurred.emit(str(e))
