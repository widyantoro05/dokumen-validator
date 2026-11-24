"""
ui/profile_wizard.py - Stepper 5 Langkah untuk Menyiapkan Profil Validasi.

Mengorkestrasi navigasi 5 langkah:
1. Rekapan Acuan
2. Dokumen Contoh & Field
3. Pencocokan Dinamis (Matching Builder)
4. Aturan Tambahan & Visual JIKA-MAKA
5. Uji & Simpan Profil JSON
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.models import (
    AturanField,
    DefinisiField,
    KondisiJikaMaka,
    ProfilValidasi,
    SkemaPencocokan,
    TabelRekap,
)
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.ui.steps.step1_recap import Step1Recap
from validator_dokumen.ui.steps.step2_field import Step2Field
from validator_dokumen.ui.steps.step3_matching import Step3Matching
from validator_dokumen.ui.steps.step4_rules import Step4Rules
from validator_dokumen.ui.steps.step5_test_save import Step5TestSave
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import PrimaryButton, SecondaryButton


class StepperBar(QWidget):
    """Bilah penunjuk langkah stepper horizontal dengan indikator angka dan status."""

    step_clicked = Signal(int)

    STEP_TITLES: ClassVar[list[str]] = [
        "1. Rekapan",
        "2. Contoh & Field",
        "3. Pencocokan",
        "4. Aturan",
        "5. Uji & Simpan",
    ]

    def __init__(self, current_step: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_step = current_step
        self.setFixedHeight(54)
        self._buttons: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(8)

        for i, title in enumerate(self.STEP_TITLES):
            btn = QPushButton(title)
            btn.setCheckable(True)
            btn.setChecked(i == self._current_step)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self.step_clicked.emit(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

            if i < len(self.STEP_TITLES) - 1:
                lbl_arrow = QLabel("→")
                lbl_arrow.setStyleSheet(f"color: {COLORS.border}; font-weight: bold;")
                layout.addWidget(lbl_arrow)

        self._update_styles()

    def set_current_step(self, step: int) -> None:
        self._current_step = max(0, min(step, len(self.STEP_TITLES) - 1))
        self._update_styles()

    def _update_styles(self) -> None:
        for i, btn in enumerate(self._buttons):
            is_active = i == self._current_step
            is_done = i < self._current_step
            btn.setChecked(is_active)

            if is_active:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {COLORS.accent};
                        color: #FFFFFF;
                        border: 1px solid {COLORS.accent};
                        border-radius: 16px;
                        padding: 6px 14px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    """
                )
            elif is_done:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {COLORS.valid_bg};
                        color: {COLORS.valid_text};
                        border: 1px solid {COLORS.valid_border};
                        border-radius: 16px;
                        padding: 6px 14px;
                        font-weight: 500;
                        font-size: 12px;
                    }}
                    """
                )
            else:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {COLORS.bg_app};
                        color: {COLORS.text_secondary};
                        border: 1px solid {COLORS.border};
                        border-radius: 16px;
                        padding: 6px 14px;
                        font-weight: 500;
                        font-size: 12px;
                    }}
                    """
                )


class ProfileWizard(QWidget):
    """Koordinator Stepper 5 Langkah untuk Membuat atau Mengedit Profil Validasi."""

    # Sinyal saat profil disimpan
    profile_saved = Signal(object, str)
    # Sinyal untuk membuka layar validasi
    open_validation_view = Signal()

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

        # Data bersama (Shared Context)
        self._tabel_rekap: TabelRekap | None = None
        self._path_rekap: str = ""
        self._contoh_pdfs: list[str] = []
        self._fields: list[DefinisiField] = []
        self._skema_list: list[SkemaPencocokan] = []
        self._aturan_field: list[AturanField] = []
        self._kondisi_list: list[KondisiJikaMaka] = []
        self._profil_id: str = ""
        self._profil_nama: str = "Profil Validasi Baru"
        self._profil_deskripsi: str = ""

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Bilah Stepper Header
        self._stepper_bar = StepperBar(0, self)
        self._stepper_bar.step_clicked.connect(self._goto_step)
        main_layout.addWidget(self._stepper_bar)

        # Garis Pembatas
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS.border};")
        main_layout.addWidget(sep)

        # Kontainer Halaman Stepper (QStackedWidget)
        self._stacked = QStackedWidget(self)

        # Langkah 1: Rekapan
        self._step1 = Step1Recap(self._rs, self)
        self._step1.recap_loaded.connect(self._on_recap_loaded)
        self._stacked.addWidget(self._step1)

        # Langkah 2: Contoh & Field
        self._step2 = Step2Field(self)
        self._step2.fields_updated.connect(self._on_fields_updated)
        self._stacked.addWidget(self._step2)

        # Langkah 3: Pencocokan
        self._step3 = Step3Matching(self)
        self._step3.schemas_updated.connect(self._on_schemas_updated)
        self._stacked.addWidget(self._step3)

        # Langkah 4: Aturan
        self._step4 = Step4Rules(self)
        self._step4.rules_updated.connect(self._on_rules_updated)
        self._stacked.addWidget(self._step4)

        # Langkah 5: Uji & Simpan
        self._step5 = Step5TestSave(self._ps, self._vs, self)
        self._step5.profile_saved.connect(self._on_profile_saved)
        self._step5.open_validation_view.connect(lambda: self.open_validation_view.emit())
        self._stacked.addWidget(self._step5)

        main_layout.addWidget(self._stacked, stretch=1)

        # Bilah Navigasi Bawah (Footer)
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS.bg_card};
                border-top: 1px solid {COLORS.border};
            }}
            """
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 0, 24, 0)

        self._btn_prev = SecondaryButton("← Kembali")
        self._btn_prev.clicked.connect(self._prev_step)
        footer_layout.addWidget(self._btn_prev)

        footer_layout.addStretch()

        self._btn_next = PrimaryButton("Lanjut →")
        self._btn_next.clicked.connect(self._next_step)
        footer_layout.addWidget(self._btn_next)

        main_layout.addWidget(footer)
        self._update_navigation_buttons()

    def _goto_step(self, step_idx: int) -> None:
        cur = self._stacked.currentIndex()
        if step_idx > cur:
            # Validasi sebelum melompat ke depan
            if not self._validate_step(cur):
                return
        self._stacked.setCurrentIndex(step_idx)
        self._stepper_bar.set_current_step(step_idx)
        self._sync_context_to_step(step_idx)
        self._update_navigation_buttons()

    def _next_step(self) -> None:
        cur = self._stacked.currentIndex()
        if not self._validate_step(cur):
            return
        if cur < 4:
            self._goto_step(cur + 1)

    def _prev_step(self) -> None:
        cur = self._stacked.currentIndex()
        if cur > 0:
            self._goto_step(cur - 1)

    def _validate_step(self, step_idx: int) -> bool:
        if step_idx == 0:
            if not self._step1.is_valid_step():
                QMessageBox.warning(
                    self,
                    "Langkah 1 Belum Lengkap",
                    "Silakan pilih berkas rekapan dan muat tabelnya terlebih dahulu.",
                )
                return False
        elif step_idx == 1:
            if not self._step2.is_valid_step():
                QMessageBox.warning(
                    self,
                    "Langkah 2 Belum Lengkap",
                    "Silakan definisikan setidaknya satu field dokumen izin.",
                )
                return False
        elif step_idx == 2:
            if not self._step3.is_valid_step():
                QMessageBox.warning(
                    self,
                    "Langkah 3 Belum Lengkap",
                    "Silakan buat setidaknya satu pasangan dengan peran KUNCI.",
                )
                return False
        return True

    def _sync_context_to_step(self, step_idx: int) -> None:
        if step_idx == 2:
            # Sinkronkan Step 3 dengan rekapan dan field
            self._step3.set_context(
                tabel_rekap=self._tabel_rekap,
                fields=self._fields,
                skema_list=self._skema_list,
            )
        elif step_idx == 3:
            # Sinkronkan Step 4 dengan rekapan dan field
            self._step4.set_context(
                tabel_rekap=self._tabel_rekap,
                fields=self._fields,
                aturan_field=self._aturan_field,
                kondisi_list=self._kondisi_list,
            )
        elif step_idx == 4:
            # Sinkronkan Step 5 dengan seluruh konfigurasi
            self._step5.set_context(
                tabel_rekap=self._tabel_rekap,
                contoh_pdfs=self._contoh_pdfs,
                fields=self._fields,
                skema_list=self._skema_list,
                aturan_field=self._aturan_field,
                kondisi_list=self._kondisi_list,
                profil_id=self._profil_id,
                profil_nama=self._profil_nama,
                profil_deskripsi=self._profil_deskripsi,
            )

    def _update_navigation_buttons(self) -> None:
        idx = self._stacked.currentIndex()
        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setVisible(idx < 4)

    def _on_recap_loaded(self, tabel: TabelRekap, path: str) -> None:
        self._tabel_rekap = tabel
        self._path_rekap = path

    def _on_fields_updated(self, fields: list[DefinisiField], pdfs: list[str]) -> None:
        self._fields = list(fields)
        self._contoh_pdfs = list(pdfs)

    def _on_schemas_updated(self, skema_list: list[SkemaPencocokan]) -> None:
        self._skema_list = list(skema_list)

    def _on_rules_updated(
        self, aturan_field: list[AturanField], kondisi_list: list[KondisiJikaMaka]
    ) -> None:
        self._aturan_field = list(aturan_field)
        self._kondisi_list = list(kondisi_list)

    def _on_profile_saved(self, profil: ProfilValidasi, path: str) -> None:
        self._profil_id = profil.id
        self._profil_nama = profil.nama
        self._profil_deskripsi = profil.deskripsi
        self.profile_saved.emit(profil, path)

    def muat_profil(self, profil: ProfilValidasi) -> None:
        """Muat profil yang sudah ada untuk diedit di wizard."""
        self._profil_id = profil.id
        self._profil_nama = profil.nama
        self._profil_deskripsi = profil.deskripsi
        self._fields = list(profil.field_dokumen)
        self._skema_list = list(profil.skema_pencocokan)
        self._aturan_field = list(profil.aturan_field)
        self._kondisi_list = list(profil.kondisi_jika_maka)

        self._step2.set_fields_and_pdfs(self._fields, self._contoh_pdfs)
        self._step3.set_context(self._tabel_rekap, self._fields, self._skema_list)
        self._step4.set_context(self._tabel_rekap, self._fields, self._aturan_field, self._kondisi_list)
        self._goto_step(0)
