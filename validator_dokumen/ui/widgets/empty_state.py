"""
ui/widgets/empty_state.py - Tampilan ramah saat data masih kosong.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import PrimaryButton


class EmptyState(QWidget):
    """
    Komponen status kosong: Ikon besar + Judul + Keterangan + Tombol aksi opsional.
    """

    def __init__(
        self,
        icon_text: str = "📁",
        title: str = "Belum Ada Data",
        description: str = "Silakan muat file dokumen atau konfigurasi terlebih dahulu.",
        button_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 36, 24, 36)

        lbl_icon = QLabel(icon_text)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet(f"font-size: 40px; color: {COLORS.text_muted};")
        layout.addWidget(lbl_icon)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS.text_primary};")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(description)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 13px; color: {COLORS.text_secondary};")
        layout.addWidget(lbl_desc)

        self.action_button: PrimaryButton | None = None
        if button_text:
            self.action_button = PrimaryButton(button_text)
            self.action_button.setFixedWidth(200)
            layout.addSpacing(6)
            layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)
