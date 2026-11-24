"""
ui/widgets/section_header.py - Header seksi standar dengan judul, deskripsi, dan aksi opsional.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from validator_dokumen.ui.theme import COLORS


class SectionHeader(QWidget):
    """
    Header seksi: Judul 14px semibold + Keterangan 12px sekunder + Aksi di kanan.
    """

    def __init__(
        self,
        title: str,
        description: str = "",
        subtitle: str = "",
        action_widget: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        desc = description or subtitle
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {COLORS.text_primary};")
        text_layout.addWidget(lbl_title)

        if desc:
            lbl_desc = QLabel(desc)
            lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.text_secondary};")
            text_layout.addWidget(lbl_desc)

        layout.addLayout(text_layout)
        layout.addStretch()

        if action_widget is not None:
            layout.addWidget(action_widget)
