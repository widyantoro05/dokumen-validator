"""
ui/widgets/labeled_field.py - Baris input berlabel dengan dukungan pesan kesalahan inline.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLayout, QVBoxLayout, QWidget

from validator_dokumen.ui.theme import COLORS


class LabeledField(QWidget):
    """
    Form row: Label teks atas + Kontrol Widget + Pesan kesalahan inline bawah (opsional).
    """

    def __init__(
        self,
        label: str,
        widget: QWidget | QLayout,
        parent: QWidget | None = None,
        required: bool = False,
    ) -> None:
        super().__init__(parent)
        self._required = required
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        req_mark = " <span style='color: #EF4444;'>*</span>" if required else ""
        self._lbl_title = QLabel(f"{label}{req_mark}")
        self._lbl_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {COLORS.text_primary}; padding: 0; margin-bottom: 2px;"
        )
        layout.addWidget(self._lbl_title)

        if isinstance(widget, QLayout):
            container = QWidget()
            container.setLayout(widget)
            self._widget = container
            layout.addWidget(container)
        else:
            self._widget = widget
            layout.addWidget(widget)

        self._lbl_error = QLabel()
        self._lbl_error.setStyleSheet("color: #DC2626; font-size: 11px; margin-top: 2px;")
        self._lbl_error.hide()
        layout.addWidget(self._lbl_error)

    def set_label(self, label: str) -> None:
        """Mengubah teks label secara dinamis."""
        req_mark = " <span style='color: #EF4444;'>*</span>" if self._required else ""
        self._lbl_title.setText(f"{label}{req_mark}")

    def set_error(self, message: str) -> None:
        if message:
            self._lbl_error.setText(message)
            self._lbl_error.show()
            self._widget.setStyleSheet("border: 1.5px solid #EF4444;")
        else:
            self._lbl_error.hide()
            self._widget.setStyleSheet("")

    def widget(self) -> QWidget:
        return self._widget
