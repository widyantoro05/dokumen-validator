"""
ui/main_window.py - Jendela Utama Aplikasi "Validator Dokumen".

Fitur:
- Sidebar kiri 200px dengan 3 navigasi:
  1. Siapkan Profil
  2. Validasi
  3. Hasil
- Bar atas: Nama profil aktif, indikator perubahan, tombol simpan.
- Stacked view dengan transisi antar layar.
- Dukungan shortcut keyboard (Ctrl+O, Ctrl+S, F5, Esc, Ctrl+F, 1/2/3/4).
- Simpan & pulihkan ukuran jendela dan preferensi via QSettings.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.constants import APP_VERSION, UI_MIN_HEIGHT, UI_MIN_WIDTH
from validator_dokumen.core.models import HasilBulk, ProfilValidasi, StatusValidasi
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.ui.profile_wizard import ProfileWizard
from validator_dokumen.ui.results_view import ResultsView
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.validation_view import ValidationView
from validator_dokumen.ui.widgets.buttons import PrimaryButton


class MainWindow(QMainWindow):
    """
    Jendela Utama Aplikasi Desktop Validator Dokumen.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Validator Dokumen")
        self.setMinimumSize(UI_MIN_WIDTH, UI_MIN_HEIGHT)

        # Inisialisasi Layanan Bisnis
        self._ps = ProfileService()
        self._rs = RecapService()
        self._vs = ValidationService()
        self._settings = QSettings("ValidatorDokumen", "ValidatorDokumen")

        self._active_profile_dirty = False
        self._setup_ui()
        self._setup_shortcuts()
        self._restore_settings()

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 1. SIDEBAR KIRI (Lebar 200px) ────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS.bg_sidebar};
                border-right: 1px solid #1E293B;
            }}
            """
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 16)
        sidebar_layout.setSpacing(8)

        # Logo & App Title
        logo_box = QVBoxLayout()
        logo_box.setSpacing(2)
        lbl_app = QLabel("Validator Dokumen")
        lbl_app.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 700;")
        lbl_ver = QLabel(f"Versi {APP_VERSION}")
        lbl_ver.setStyleSheet("color: #94A3B8; font-size: 11px;")
        logo_box.addWidget(lbl_app)
        logo_box.addWidget(lbl_ver)
        sidebar_layout.addLayout(logo_box)
        sidebar_layout.addSpacing(20)

        # Tombol Navigasi Sidebar
        self._btn_group_nav = QButtonGroup(self)
        self._btn_group_nav.setExclusive(True)

        self._btn_nav_profil = self._buat_nav_btn("1. Siapkan Profil", 0)
        self._btn_nav_validasi = self._buat_nav_btn("2. Validasi", 1)
        self._btn_nav_hasil = self._buat_nav_btn("3. Hasil", 2)

        sidebar_layout.addWidget(self._btn_nav_profil)
        sidebar_layout.addWidget(self._btn_nav_validasi)
        sidebar_layout.addWidget(self._btn_nav_hasil)
        sidebar_layout.addStretch()

        # Footer Sidebar
        btn_log = QPushButton("Buka Folder Log")
        btn_log.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #FFFFFF;
                border-color: #64748B;
            }
            """
        )
        btn_log.clicked.connect(self._buka_folder_log)
        sidebar_layout.addWidget(btn_log)

        root_layout.addWidget(sidebar)

        # ── 2. AREA KONTEN KANAN ─────────────────────────────────────────────
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Bar Atas (Header Bar)
        top_bar = QFrame()
        top_bar.setFixedHeight(54)
        top_bar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS.bg_card};
                border-bottom: 1px solid {COLORS.border};
            }}
            """
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        top_layout.setSpacing(12)

        self._lbl_profil_name = QLabel("Profil Aktif: Profil Contoh - Izin Usaha")
        self._lbl_profil_name.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {COLORS.text_primary};"
        )
        top_layout.addWidget(self._lbl_profil_name)

        # Indikator Belum Disimpan (titik oranye)
        self._lbl_dirty = QLabel("● Belum disimpan")
        self._lbl_dirty.setStyleSheet("color: #EA580C; font-size: 11px; font-weight: 600;")
        self._lbl_dirty.hide()
        top_layout.addWidget(self._lbl_dirty)

        top_layout.addStretch()

        self._btn_top_save = PrimaryButton("Simpan Profil")
        self._btn_top_save.setFixedSize(120, 32)
        self._btn_top_save.clicked.connect(self._simpan_profil_aktif)
        top_layout.addWidget(self._btn_top_save)

        content_layout.addWidget(top_bar)

        # Stacked Widget (Multi-Screen)
        self._stacked = QStackedWidget()

        # Layar 0: Siapkan Profil (ProfileWizard 5 Langkah)
        self._wizard = ProfileWizard(self._ps, self._rs, self._vs, self)
        self._wizard.profile_saved.connect(self._on_profile_saved)
        self._wizard.open_validation_view.connect(lambda: self._switch_nav(1))
        self._stacked.addWidget(self._wizard)

        # Layar 1: Validasi
        self._view_validasi = ValidationView(self._ps, self._rs, self._vs, self)
        self._view_validasi.validation_finished.connect(self._on_validation_finished)
        self._stacked.addWidget(self._view_validasi)

        # Layar 2: Hasil
        self._view_hasil = ResultsView(self)
        self._stacked.addWidget(self._view_hasil)

        content_layout.addWidget(self._stacked, stretch=1)
        root_layout.addWidget(content_area, stretch=1)

        # Default ke Layar Validasi
        self._btn_nav_validasi.setChecked(True)
        self._stacked.setCurrentIndex(1)

        # Menu Bar
        self._setup_menu_bar()

    def _buat_nav_btn(self, text: str, page_idx: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setMinimumHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: #CBD5E1;
                border: none;
                border-radius: 6px;
                padding-left: 14px;
                text-align: left;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.bg_sidebar_hover};
                color: #FFFFFF;
            }}
            QPushButton:checked {{
                background-color: {COLORS.bg_sidebar_active};
                color: #FFFFFF;
                font-weight: 600;
            }}
            """
        )
        self._btn_group_nav.addButton(btn, page_idx)
        btn.clicked.connect(lambda: self._switch_nav(page_idx))
        return btn

    def _switch_nav(self, page_idx: int) -> None:
        self._stacked.setCurrentIndex(page_idx)
        if page_idx == 0:
            self._btn_nav_profil.setChecked(True)
        elif page_idx == 1:
            self._btn_nav_validasi.setChecked(True)
        elif page_idx == 2:
            self._btn_nav_hasil.setChecked(True)

    def _setup_menu_bar(self) -> None:
        bar = self.menuBar()

        # Menu Berkas
        menu_berkas = bar.addMenu("&Berkas")

        act_buka = QAction("&Buka Rekapan...", self)
        act_buka.setShortcut(QKeySequence.StandardKey.Open)
        act_buka.triggered.connect(self._view_validasi._pilih_rekap)
        menu_berkas.addAction(act_buka)

        act_simpan = QAction("&Simpan Profil", self)
        act_simpan.setShortcut(QKeySequence.StandardKey.Save)
        act_simpan.triggered.connect(self._simpan_profil_aktif)
        menu_berkas.addAction(act_simpan)

        menu_berkas.addSeparator()

        act_keluar = QAction("&Keluar", self)
        act_keluar.setShortcut(QKeySequence("Alt+F4"))
        act_keluar.triggered.connect(self.close)
        menu_berkas.addAction(act_keluar)

        # Menu Bantuan
        menu_bantuan = bar.addMenu("&Bantuan")

        act_log = QAction("Buka Folder Log", self)
        act_log.triggered.connect(self._buka_folder_log)
        menu_bantuan.addAction(act_log)

        act_tentang = QAction("Tentang Validator Dokumen", self)
        act_tentang.triggered.connect(self._show_about_dialog)
        menu_bantuan.addAction(act_tentang)

    def _setup_shortcuts(self) -> None:
        """Shortcut keyboard sesuai spesifikasi."""
        # F5 = Mulai Validasi
        QShortcut(QKeySequence("F5"), self, self._view_validasi._mulai_validasi)

        # Esc = Batalkan proses
        QShortcut(QKeySequence("Esc"), self, self._view_validasi._batalkan_validasi)

        # Ctrl+F = Fokus ke pencarian di layar Hasil
        def focus_search() -> None:
            self._switch_nav(2)
            self._view_hasil._txt_search.setFocus()
            self._view_hasil._txt_search.selectAll()

        QShortcut(QKeySequence.StandardKey.Find, self, focus_search)

        # 1/2/3/4 = Filter Status di Layar Hasil
        QShortcut(
            QKeySequence("1"),
            self,
            lambda: self._view_hasil._on_stat_card_clicked(StatusValidasi.VALID),
        )
        QShortcut(
            QKeySequence("2"),
            self,
            lambda: self._view_hasil._on_stat_card_clicked(StatusValidasi.TIDAK_VALID),
        )
        QShortcut(
            QKeySequence("3"),
            self,
            lambda: self._view_hasil._on_stat_card_clicked(StatusValidasi.PERLU_DICEK),
        )
        QShortcut(
            QKeySequence("4"),
            self,
            lambda: self._view_hasil._on_stat_card_clicked(StatusValidasi.TIDAK_BISA_DIBACA),
        )

    def _on_validation_finished(self, result: Any) -> None:
        """Pindah ke layar Hasil dan tampilkan ringkasan setelah selesai."""
        if isinstance(result, HasilBulk):
            self._view_hasil.display_bulk_results(result)
            self._switch_nav(2)

            # Dialog ringkasan
            msg = (
                f"Validasi bulk selesai ({result.total} dokumen):<br><br>"
                f"• <b>✔ VALID</b>: {result.valid}<br>"
                f"• <b>✖ TIDAK VALID</b>: {result.tidak_valid}<br>"
                f"• <b>⚠ PERLU DICEK</b>: {result.perlu_dicek}<br>"
                f"• <b>⦸ TIDAK TERBACA</b>: {result.tidak_bisa_dibaca}<br><br>"
                f"Hasil disimpan di: <code>{result.folder_output}</code>"
            )
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Validasi Bulk Selesai")
            dlg.setText(msg)
            btn_open = dlg.addButton("Buka Folder Hasil", QMessageBox.ButtonRole.ActionRole)
            dlg.addButton("Tutup", QMessageBox.ButtonRole.RejectRole)
            dlg.exec()

            if dlg.clickedButton() == btn_open:
                self._view_hasil._buka_folder_hasil()

    def _on_profile_saved(self, profil: ProfilValidasi, path: str) -> None:
        self._lbl_profil_aktif.setText(f"Profil Aktif: <b>{profil.nama}</b>")
        self._lbl_dirty.hide()
        self._view_validasi.muat_daftar_profil()

    def _simpan_profil_aktif(self) -> None:
        if self._stacked.currentIndex() == 0:
            self._wizard._step5._simpan_profil()
        else:
            QMessageBox.information(self, "Simpan Profil", "Buka layar 'Siapkan Profil' untuk menyimpan konfigurasi.")

    def _buka_folder_log(self) -> None:
        import tempfile

        base_env = os.environ.get("LOCALAPPDATA")
        log_dir = (
            Path(base_env) / "ValidatorDokumen" / "logs"
            if base_env
            else Path(tempfile.gettempdir()) / "ValidatorDokumen" / "logs"
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{log_dir}"')

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "Tentang Validator Dokumen",
            f"<b>Validator Dokumen</b> v{APP_VERSION}<br>"
            "Aplikasi Pencocokan & Validasi Dokumen Acuan Dinamis.<br>"
            "Dibuat dengan Python 3.11 dan PySide6.",
        )

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        """Simpan ukuran dan preferensi jendela sebelum keluar."""
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def _restore_settings(self) -> None:
        geom = self._settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)
