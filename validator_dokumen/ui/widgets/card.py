"""
ui/widgets/card.py - Kontainer kartu putih dengan border dan border-radius 8px.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from validator_dokumen.ui.theme import COLORS


class Card(QFrame):
    """
    Kontainer kartu bergaya modern: latar putih, border halus, padding 16px.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            Card {{
                background-color: {COLORS.bg_card};
                border: 1.5px solid {COLORS.border};
                border-radius: 8px;
            }}
            """
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

    def layout(self) -> QVBoxLayout:
        return self._layout
