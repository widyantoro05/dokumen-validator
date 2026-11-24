"""
ui/widgets/stat_card.py - Kartu ringkasan statistik status yang bisa diklik untuk filter.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from validator_dokumen.core.models import StatusValidasi
from validator_dokumen.ui.theme import COLORS, status_color_pair, status_icon_and_label


class StatCard(QFrame):
    """
    Kartu statistik ringkasan per status.
    Klik pada kartu akan memancarkan sinyal `clicked(status)` untuk memfilter tabel.
    """

    clicked = Signal(object)  # Memancarkan StatusValidasi

    def __init__(
        self,
        status: StatusValidasi,
        count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._status = status
        self._count = count
        self._active = False

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._text_col, self._bg_col, self._border_col = status_color_pair(status)
        self._icon, self._label_text = status_icon_and_label(status)

        self._setup_ui()
        self._update_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self._lbl_icon = QLabel(self._icon)
        self._lbl_icon.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {self._text_col};"
        )
        header_layout.addWidget(self._lbl_icon)

        self._lbl_title = QLabel(self._label_text)
        self._lbl_title.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {COLORS.text_secondary};"
        )
        header_layout.addWidget(self._lbl_title)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        self._lbl_count = QLabel(str(self._count))
        self._lbl_count.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {self._text_col};"
        )
        layout.addWidget(self._lbl_count)

    def set_count(self, count: int) -> None:
        self._count = count
        self._lbl_count.setText(str(count))

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_style()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._status)
        super().mousePressEvent(event)

    def _update_style(self) -> None:
        border_width = "2px" if self._active else "1px"
        border_color = self._text_col if self._active else COLORS.border
        bg = self._bg_col if self._active else COLORS.bg_card

        self.setStyleSheet(
            f"""
            StatCard {{
                background-color: {bg};
                border: {border_width} solid {border_color};
                border-radius: 8px;
            }}
            StatCard:hover {{
                border-color: {self._border_col};
                background-color: {self._bg_col};
            }}
            """
        )
