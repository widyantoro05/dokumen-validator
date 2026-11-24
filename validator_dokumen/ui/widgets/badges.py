"""
ui/widgets/badges.py - StatusBadge untuk menampilkan status validasi secara konsisten.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from validator_dokumen.core.models import StatusValidasi
from validator_dokumen.ui.theme import status_color_pair, status_icon_and_label


class StatusBadge(QLabel):
    """
    Badge status membulat: Ikon + Teks + Warna (misal: ✔ VALID, ✖ TIDAK VALID).
    """

    def __init__(
        self,
        status: StatusValidasi | None = None,
        parent: QWidget | None = None,
        large: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._large = large
        if status is not None:
            self.set_status(status)

    def set_status(self, status: StatusValidasi) -> None:
        icon, label = status_icon_and_label(status)
        text_col, bg_col, border_col = status_color_pair(status)

        self.setText(f"{icon} {label}")
        font_size = "13px" if self._large else "11px"
        padding = "4px 12px" if self._large else "2px 8px"
        radius = "12px" if self._large else "10px"

        self.setStyleSheet(
            f"""
            StatusBadge {{
                color: {text_col};
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: {radius};
                padding: {padding};
                font-weight: 700;
                font-size: {font_size};
            }}
            """
        )
