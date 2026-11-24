"""
ui/widgets/info_banner.py - Banner pesan informasi, peringatan, atau error.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from validator_dokumen.ui.theme import COLORS


class InfoBanner(QFrame):
    """
    Kotak pesan alert informatif: 'info' (biru), 'warning' (kuning), atau 'error' (merah).
    """

    def __init__(
        self,
        message: str = "",
        banner_type: str = "info",  # 'info' | 'warning' | 'error' | 'success'
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._lbl_icon = QLabel()
        self._lbl_icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._lbl_icon)

        self._lbl_message = QLabel(message)
        self._lbl_message.setWordWrap(True)
        layout.addWidget(self._lbl_message, stretch=1)

        self.set_type(banner_type)

    def set_message(self, message: str) -> None:
        self._lbl_message.setText(message)

    def set_state(self, message: str, banner_type: str = "info") -> None:
        self.set_message(message)
        self.set_type(banner_type)

    def set_type(self, banner_type: str) -> None:
        if banner_type == "error":
            bg = COLORS.tidak_valid_bg
            border = COLORS.tidak_valid_border
            text = COLORS.tidak_valid_text
            icon = "✖"
        elif banner_type == "warning":
            bg = COLORS.perlu_dicek_bg
            border = COLORS.perlu_dicek_border
            text = COLORS.perlu_dicek_text
            icon = "⚠"
        elif banner_type == "success":
            bg = COLORS.valid_bg
            border = COLORS.valid_border
            text = COLORS.valid_text
            icon = "✔"
        else:
            bg = "#EFF6FF"
            border = "#BFDBFE"
            text = "#1E40AF"
            icon = "ℹ"

        self._lbl_icon.setText(icon)
        self._lbl_icon.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text};")
        self._lbl_message.setStyleSheet(f"color: {text}; font-size: 12px; font-weight: 500;")

        self.setStyleSheet(
            f"""
            InfoBanner {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            """
        )
