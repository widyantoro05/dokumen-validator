"""
ui/widgets/buttons.py - Tombol standar: PrimaryButton, SecondaryButton, DangerButton.
"""

from __future__ import annotations

from PySide6.QtGui import QCursor, Qt
from PySide6.QtWidgets import QPushButton, QWidget

from validator_dokumen.ui.theme import COLORS


class PrimaryButton(QPushButton):
    """
    Tombol aksi utama: biru penuh (#2563EB), teks putih, radius 6px.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(38)
        self.setStyleSheet(
            f"""
            PrimaryButton {{
                background-color: {COLORS.accent};
                color: {COLORS.text_white};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }}
            PrimaryButton:hover {{
                background-color: {COLORS.accent_hover};
            }}
            PrimaryButton:pressed {{
                background-color: {COLORS.accent_pressed};
            }}
            PrimaryButton:disabled {{
                background-color: {COLORS.border};
                color: {COLORS.text_muted};
            }}
            """
        )


class SecondaryButton(QPushButton):
    """
    Tombol aksi sekunder: latar transparan/putih, border outline, teks primer.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(38)
        self.setStyleSheet(
            f"""
            SecondaryButton {{
                background-color: {COLORS.bg_card};
                color: {COLORS.text_primary};
                border: 1px solid {COLORS.border};
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 500;
                font-size: 13px;
            }}
            SecondaryButton:hover {{
                background-color: {COLORS.bg_hover};
                border-color: {COLORS.border_subtle};
            }}
            SecondaryButton:pressed {{
                background-color: {COLORS.border};
            }}
            SecondaryButton:disabled {{
                background-color: {COLORS.bg_app};
                color: {COLORS.text_muted};
                border-color: {COLORS.border};
            }}
            """
        )


class DangerButton(QPushButton):
    """
    Tombol aksi berbahaya/hapus: merah outline atau latar merah tipis.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(38)
        self.setStyleSheet(
            f"""
            DangerButton {{
                background-color: {COLORS.tidak_valid_bg};
                color: {COLORS.tidak_valid_text};
                border: 1px solid {COLORS.tidak_valid_border};
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }}
            DangerButton:hover {{
                background-color: #FCA5A5;
            }}
            DangerButton:pressed {{
                background-color: #F87171;
                color: {COLORS.text_white};
            }}
            DangerButton:disabled {{
                background-color: {COLORS.bg_app};
                color: {COLORS.text_muted};
                border-color: {COLORS.border};
            }}
            """
        )
