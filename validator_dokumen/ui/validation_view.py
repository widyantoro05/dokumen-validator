"""
ui/validation_view.py - Layar "Validasi" (Pemilihan Profil, Rekapan, Target Dokumen & Progres).

Mendukung mode Bulk Folder dan 1 File, opsi lanjutan (OCR, output, paralel),
dan progres real-time dengan tombol batal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.models import HasilBulk, ProfilValidasi
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import DangerButton, PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.card import Card
from validator_dokumen.ui.widgets.info_banner import InfoBanner
from validator_dokumen.ui.widgets.labeled_field import LabeledField
from validator_dokumen.ui.widgets.section_header import SectionHeader
from validator_dokumen.workers.validation_worker import ValidationWorker


class ValidationView(QWidget):
    """
    Tampilan layar 'Validasi'.
    """

    validation_finished = Signal(object)  # Memancarkan HasilBulk atau HasilValidasiDokumen

    def __init__(
        self,
        profile_service: ProfileService,
        recap_service: RecapService,
        validation_service: ValidationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ps = profile_service
        self._rs = recap_service
        self._vs = validation_service

        self._current_profil: ProfilValidasi | None = None
        self._worker: ValidationWorker | None = None

        self._setup_ui()
        self.refresh_profiles()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Kontainer scroll agar tampilan tidak pernah terhimpit di resolusi / DPI scaling berapapun
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(16)

        # Header Layar
        header = SectionHeader(
            title="Validasi Dokumen",
            description="Pilih profil pencocokan, file rekapan acuan, dan tentukan dokumen PDF yang akan divalidasi.",
        )
        main_layout.addWidget(header)

        # Banner Notifikasi jika ada peringatan
        self._banner = InfoBanner(banner_type="info")
        self._banner.hide()
        main_layout.addWidget(self._banner)

        # Kartu Konfigurasi Utama
        card_config = Card()
        cfg_layout = card_config.layout()
        cfg_layout.setSpacing(16)

        # 1. Pilihan Profil
        w_profil = QWidget()
        row_profil = QHBoxLayout(w_profil)
        row_profil.setContentsMargins(0, 0, 0, 0)
        row_profil.setSpacing(8)
        self._combo_profil = QComboBox()
        self._combo_profil.setMinimumHeight(38)
        self._combo_profil.currentIndexChanged.connect(self._on_profil_changed)
        btn_refresh_profil = SecondaryButton("Segarkan")
        btn_refresh_profil.setMinimumHeight(38)
        btn_refresh_profil.clicked.connect(self.refresh_profiles)
        row_profil.addWidget(self._combo_profil, stretch=1)
        row_profil.addWidget(btn_refresh_profil)
        self._field_profil = LabeledField("Profil Pencocokan", w_profil, required=True)
        cfg_layout.addWidget(self._field_profil)

        # 2. Pilihan Rekapan
        w_rekap = QWidget()
        row_rekap = QHBoxLayout(w_rekap)
        row_rekap.setContentsMargins(0, 0, 0, 0)
        row_rekap.setSpacing(8)
        self._txt_rekap = QLineEdit()
        self._txt_rekap.setMinimumHeight(38)
        self._txt_rekap.setPlaceholderText("Pilih file Excel rekapan acuan (.xlsx)...")
        self._txt_rekap.setReadOnly(True)
        btn_pilih_rekap = SecondaryButton("Pilih Rekapan...")
        btn_pilih_rekap.setMinimumHeight(38)
        btn_pilih_rekap.clicked.connect(self._pilih_rekap)
        row_rekap.addWidget(self._txt_rekap, stretch=1)
        row_rekap.addWidget(btn_pilih_rekap)
        self._field_rekap = LabeledField("Dokumen Acuan (Rekapan Excel)", w_rekap, required=True)
        cfg_layout.addWidget(self._field_rekap)

        # 3. Mode Validasi: Bulk Folder vs 1 File
        w_mode = QWidget()
        row_mode = QHBoxLayout(w_mode)
        row_mode.setContentsMargins(0, 2, 0, 2)
        row_mode.setSpacing(24)
        self._radio_bulk = QRadioButton("Validasi Folder (Bulk)")
        self._radio_bulk.setChecked(True)
        self._radio_bulk.toggled.connect(self._on_mode_changed)
        self._radio_single = QRadioButton("Validasi 1 File Dokumen")
        row_mode.addWidget(self._radio_bulk)
        row_mode.addWidget(self._radio_single)
        row_mode.addStretch()
        self._field_mode = LabeledField("Mode Validasi", w_mode)
        cfg_layout.addWidget(self._field_mode)

        # 4. Target Input PDF
        w_target = QWidget()
        row_target = QHBoxLayout(w_target)
        row_target.setContentsMargins(0, 0, 0, 0)
        row_target.setSpacing(8)
        self._txt_target = QLineEdit()
        self._txt_target.setMinimumHeight(38)
        self._txt_target.setPlaceholderText("Pilih folder yang memuat file PDF...")
        btn_pilih_target = SecondaryButton("Pilih...")
        btn_pilih_target.setMinimumHeight(38)
        btn_pilih_target.clicked.connect(self._pilih_target)
        row_target.addWidget(self._txt_target, stretch=1)
        row_target.addWidget(btn_pilih_target)
        self._field_target = LabeledField("Folder PDF Target", w_target, required=True)
        cfg_layout.addWidget(self._field_target)

        self._chk_subfolder = QCheckBox("Sertakan file di dalam subfolder")
        self._chk_subfolder.setStyleSheet("margin-top: 4px; font-size: 13px;")
        cfg_layout.addWidget(self._chk_subfolder)

        main_layout.addWidget(card_config)

        # Kartu Opsi Lanjutan (Collapsible)
        self._group_advanced = QGroupBox("Opsi Lanjutan")
        self._group_advanced.setCheckable(True)
        self._group_advanced.setChecked(False)
        self._group_advanced.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {COLORS.bg_card};
                border: 1.5px solid {COLORS.border};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 20px;
                font-weight: 600;
                font-size: 13px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 2px 8px;
                background-color: {COLORS.bg_card};
                color: {COLORS.text_primary};
                border-radius: 4px;
            }}
            """
        )
        adv_layout = QVBoxLayout(self._group_advanced)
        adv_layout.setContentsMargins(16, 16, 16, 16)
        adv_layout.setSpacing(14)

        row_ocr = QHBoxLayout()
        row_ocr.setContentsMargins(0, 0, 0, 0)
        row_ocr.setSpacing(16)
        self._chk_paksa_ocr = QCheckBox("Paksa OCR untuk semua halaman dokumen")
        row_ocr.addWidget(self._chk_paksa_ocr)
        row_ocr.addSpacing(16)

        lbl_ocr = QLabel("Ambang Confidence OCR Min (%):")
        lbl_ocr.setStyleSheet(f"color: {COLORS.text_secondary}; font-size: 13px;")
        row_ocr.addWidget(lbl_ocr)
        self._spin_ocr_conf = QSpinBox()
        self._spin_ocr_conf.setRange(10, 100)
        self._spin_ocr_conf.setValue(80)
        self._spin_ocr_conf.setMinimumHeight(36)
        self._spin_ocr_conf.setFixedWidth(80)
        row_ocr.addWidget(self._spin_ocr_conf)
        row_ocr.addStretch()
        adv_layout.addLayout(row_ocr)

        # Opsi Pindah File
        self._chk_pindah_file = QCheckBox(
            "Pindahkan file asli ke folder hasil (Default: Salin, file asli aman)"
        )
        adv_layout.addWidget(self._chk_pindah_file)

        # Folder Output Kustom
        w_out = QWidget()
        row_out = QHBoxLayout(w_out)
        row_out.setContentsMargins(0, 0, 0, 0)
        row_out.setSpacing(8)
        self._txt_output_custom = QLineEdit()
        self._txt_output_custom.setMinimumHeight(38)
        self._txt_output_custom.setPlaceholderText("Default: dibuat di samping folder input")
        btn_pilih_out = SecondaryButton("Pilih...")
        btn_pilih_out.setMinimumHeight(38)
        btn_pilih_out.clicked.connect(self._pilih_folder_output)
        row_out.addWidget(self._txt_output_custom, stretch=1)
        row_out.addWidget(btn_pilih_out)
        self._field_out = LabeledField("Folder Output Kustom (Opsional)", w_out)
        adv_layout.addWidget(self._field_out)

        main_layout.addWidget(self._group_advanced)
        main_layout.addStretch()

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area, stretch=1)

        # Bilah Aksi Bawah (Sticky Footer dengan Border Atas yang Tegas)
        self._bottom_bar = QFrame()
        self._bottom_bar.setObjectName("validation_bottom_bar")
        self._bottom_bar.setStyleSheet(
            f"""
            QFrame#validation_bottom_bar {{
                background-color: {COLORS.bg_card};
                border-top: 1.5px solid {COLORS.border};
            }}
            """
        )
        bottom_layout = QVBoxLayout(self._bottom_bar)
        bottom_layout.setContentsMargins(24, 14, 24, 14)
        bottom_layout.setSpacing(10)

        # Panel Progres (tampil saat validasi berjalan)
        self._progress_panel = QWidget()
        prog_layout = QVBoxLayout(self._progress_panel)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(6)

        row_status = QHBoxLayout()
        self._lbl_progress_status = QLabel("Memulai proses validasi...")
        self._lbl_progress_status.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {COLORS.text_secondary};"
        )
        self._lbl_progress_eta = QLabel("~00:00")
        self._lbl_progress_eta.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {COLORS.accent};"
        )
        row_status.addWidget(self._lbl_progress_status)
        row_status.addStretch()
        row_status.addWidget(self._lbl_progress_eta)
        prog_layout.addLayout(row_status)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        prog_layout.addWidget(self._progress_bar)

        self._progress_panel.hide()
        bottom_layout.addWidget(self._progress_panel)

        # Baris Tombol Aksi Bawah
        row_action = QHBoxLayout()
        row_action.setContentsMargins(0, 0, 0, 0)
        row_action.setSpacing(12)

        self._lbl_bottom_hint = QLabel("Pastikan file rekapan acuan dan folder target sudah dipilih.")
        self._lbl_bottom_hint.setStyleSheet(
            f"font-size: 12px; color: {COLORS.text_secondary};"
        )
        row_action.addWidget(self._lbl_bottom_hint)
        row_action.addStretch()

        self._btn_cancel = DangerButton("Batal")
        self._btn_cancel.setFixedSize(110, 42)
        self._btn_cancel.clicked.connect(self._batalkan_validasi)
        self._btn_cancel.hide()
        row_action.addWidget(self._btn_cancel)

        self._btn_start = PrimaryButton("▶ Mulai Validasi")
        self._btn_start.setFixedSize(190, 42)
        self._btn_start.clicked.connect(self._mulai_validasi)
        row_action.addWidget(self._btn_start)

        bottom_layout.addLayout(row_action)
        outer_layout.addWidget(self._bottom_bar)

    def refresh_profiles(self) -> None:
        """Segarkan daftar profil dari disk."""
        self._combo_profil.clear()
        daftar = self._ps.daftar_profil()
        if not daftar:
            # Buat profil contoh otomatis jika belum ada
            self._ps.buat_profil_contoh()
            daftar = self._ps.daftar_profil()

        for _pid, nama, path in daftar:
            self._combo_profil.addItem(nama, userData=str(path))

    def _on_profil_changed(self) -> None:
        path_str = self._combo_profil.currentData()
        if not path_str:
            return
        try:
            self._current_profil = self._ps.muat(Path(path_str))
            self._banner.hide()
        except Exception as e:
            self._banner.set_message(f"Gagal memuat profil: {e}")
            self._banner.set_type("error")
            self._banner.show()

    def _on_mode_changed(self) -> None:
        is_bulk = self._radio_bulk.isChecked()
        if is_bulk:
            self._field_target.set_label("Folder PDF Target")
            self._txt_target.setPlaceholderText("Pilih folder yang memuat file PDF...")
            self._chk_subfolder.show()
        else:
            self._field_target.set_label("File PDF Target")
            self._txt_target.setPlaceholderText("Pilih 1 file PDF yang akan diperiksa...")
            self._chk_subfolder.hide()

    def _pilih_rekap(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Rekapan Acuan",
            filter="File Excel (*.xlsx *.xls)",
        )
        if path:
            self._txt_rekap.setText(path)
            # Muat dan verifikasi kolom
            try:
                tabel = self._rs.muat_excel(Path(path))
                if self._current_profil:
                    hilang = self._ps.deteksi_kolom_hilang(self._current_profil, list(tabel.kolom))
                    if hilang:
                        teks = "Kolom rekapan berikut hilang atau berbeda dari profil:<br>"
                        for h in hilang:
                            teks += f"• Kolom <b>'{h['kolom_rekap']}'</b> untuk field '{h['field_dokumen']}'<br>"
                        self._banner.set_message(teks)
                        self._banner.set_type("warning")
                        self._banner.show()
                    else:
                        self._banner.set_message(
                            f"Rekapan valid: {len(tabel.baris)} baris, {len(tabel.kolom)} kolom."
                        )
                        self._banner.set_type("success")
                        self._banner.show()
            except Exception as e:
                self._banner.set_message(f"Gagal membaca rekapan: {e}")
                self._banner.set_type("error")
                self._banner.show()

    def _pilih_target(self) -> None:
        if self._radio_bulk.isChecked():
            path = QFileDialog.getExistingDirectory(self, "Pilih Folder Dokumen PDF")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Pilih File Dokumen PDF", filter="File PDF (*.pdf)"
            )
        if path:
            self._txt_target.setText(path)

    def _pilih_folder_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pilih Folder Output Kustom")
        if path:
            self._txt_output_custom.setText(path)

    def _mulai_validasi(self) -> None:
        if not self._current_profil:
            self._banner.set_message("Pilih profil validasi terlebih dahulu.")
            self._banner.set_type("error")
            self._banner.show()
            return

        rekap_path_str = self._txt_rekap.text().strip()
        if not rekap_path_str or not Path(rekap_path_str).exists():
            self._banner.set_message("File rekapan acuan belum dipilih atau tidak ditemukan.")
            self._banner.set_type("error")
            self._banner.show()
            return

        target_path_str = self._txt_target.text().strip()
        if not target_path_str or not Path(target_path_str).exists():
            self._banner.set_message(
                "Target file atau folder PDF belum dipilih atau tidak ditemukan."
            )
            self._banner.set_type("error")
            self._banner.show()
            return

        # Pastikan tabel & indeks rekapan siap
        try:
            tabel = self._rs.muat_excel(Path(rekap_path_str))
            kolom_butuh = []
            for skema in self._current_profil.skema_pencocokan:
                for pas in skema.pasangan:
                    if pas.kolom_rekap not in kolom_butuh:
                        kolom_butuh.append(pas.kolom_rekap)

            indeks = self._rs.bangun_indeks(kolom_butuh)
        except Exception as e:
            self._banner.set_message(f"Gagal mempersiapkan indeks rekapan: {e}")
            self._banner.set_type("error")
            self._banner.show()
            return

        # UI state running
        self._btn_start.hide()
        self._btn_cancel.show()
        self._progress_panel.show()
        self._progress_bar.setValue(0)
        self._lbl_progress_status.setText("Memulai proses validasi...")

        folder_out = (
            Path(self._txt_output_custom.text().strip())
            if self._txt_output_custom.text().strip()
            else None
        )

        # Jalankan di Worker Thread
        self._worker = ValidationWorker(
            validation_service=self._vs,
            profil=self._current_profil,
            indeks=indeks,
            tabel_rekap=tabel,
            input_path=Path(target_path_str),
            is_bulk=self._radio_bulk.isChecked(),
            sertakan_subfolder=self._chk_subfolder.isChecked(),
            pindah_file=self._chk_pindah_file.isChecked(),
            folder_output=folder_out,
            parent=self,
        )

        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished_bulk.connect(self._on_worker_finished_bulk)
        self._worker.finished_single.connect(self._on_worker_finished_single)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.start()

    def _batalkan_validasi(self) -> None:
        if self._worker:
            self._lbl_progress_status.setText("Membatalkan proses...")
            self._worker.cancel()

    def _on_worker_progress(self, current: int, total: int, file_name: str, eta_str: str) -> None:
        pct = int((current / total) * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._lbl_progress_status.setText(f"[{current}/{total}] Memvalidasi: {file_name}")
        self._lbl_progress_eta.setText(eta_str)

    def _on_worker_finished_bulk(self, bulk_result: HasilBulk) -> None:
        self._btn_cancel.hide()
        self._btn_start.show()
        self._progress_panel.hide()
        self.validation_finished.emit(bulk_result)

    def _on_worker_finished_single(self, doc_result: Any) -> None:
        self._btn_cancel.hide()
        self._btn_start.show()
        self._progress_panel.hide()
        self.validation_finished.emit(doc_result)

    def _on_worker_error(self, error_msg: str) -> None:
        self._btn_cancel.hide()
        self._btn_start.show()
        self._progress_panel.hide()
        self._banner.set_message(f"Error saat validasi: {error_msg}")
        self._banner.set_type("error")
        self._banner.show()
