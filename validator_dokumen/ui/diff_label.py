"""
ui/diff_label.py - Komponen visual diff tingkat karakter untuk perbandingan nilai dokumen vs rekapan.

Menampilkan teks dengan perbedaan karakter disorot latar merah/hijau muda
sehingga perbedaan seperti "123-ABC" vs "123-ABD" langsung terlihat jelas.
"""

from __future__ import annotations

import difflib
import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from validator_dokumen.ui.theme import COLORS


def _render_char_diff_html(text_a: str, text_b: str) -> tuple[str, str]:
    """
    Menghasilkan 2 string HTML (versi dokumen dan versi rekapan)
    dengan karakter yang berbeda disorot warna merah/hijau.
    """
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    html_a = []
    html_b = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        seg_a = html.escape(text_a[i1:i2])
        seg_b = html.escape(text_b[j1:j2])

        if tag == "equal":
            html_a.append(seg_a)
            html_b.append(seg_b)
        elif tag == "replace":
            html_a.append(
                f"<span style='background-color: {COLORS.tidak_valid_bg}; color: {COLORS.tidak_valid_text}; font-weight: bold;'>{seg_a}</span>"
            )
            html_b.append(
                f"<span style='background-color: {COLORS.valid_bg}; color: {COLORS.valid_text}; font-weight: bold;'>{seg_b}</span>"
            )
        elif tag == "delete":
            html_a.append(
                f"<span style='background-color: {COLORS.tidak_valid_bg}; color: {COLORS.tidak_valid_text}; font-weight: bold;'>{seg_a}</span>"
            )
        elif tag == "insert":
            html_b.append(
                f"<span style='background-color: {COLORS.valid_bg}; color: {COLORS.valid_text}; font-weight: bold;'>{seg_b}</span>"
            )

    return "".join(html_a), "".join(html_b)


class DiffLabel(QWidget):
    """
    Widget penampil diff komparasi Dokumen vs Rekapan.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Baris Dokumen
        row_dok = QHBoxLayout()
        row_dok.setSpacing(8)
        lbl_dok_tag = QLabel("Dokumen:")
        lbl_dok_tag.setFixedWidth(70)
        lbl_dok_tag.setStyleSheet(
            f"font-weight: 600; color: {COLORS.text_secondary}; font-size: 11px;"
        )
        row_dok.addWidget(lbl_dok_tag)

        self._lbl_dok = QLabel()
        self._lbl_dok.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._lbl_dok.setStyleSheet("font-family: monospace; font-size: 12px;")
        row_dok.addWidget(self._lbl_dok, stretch=1)
        layout.addLayout(row_dok)

        # Baris Rekapan
        row_rek = QHBoxLayout()
        row_rek.setSpacing(8)
        lbl_rek_tag = QLabel("Rekapan:")
        lbl_rek_tag.setFixedWidth(70)
        lbl_rek_tag.setStyleSheet(
            f"font-weight: 600; color: {COLORS.text_secondary}; font-size: 11px;"
        )
        row_rek.addWidget(lbl_rek_tag)

        self._lbl_rek = QLabel()
        self._lbl_rek.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._lbl_rek.setStyleSheet("font-family: monospace; font-size: 12px;")
        row_rek.addWidget(self._lbl_rek, stretch=1)
        layout.addLayout(row_rek)

    def set_values(self, doc_val: str, recap_val: str) -> None:
        """Set nilai dokumen dan rekapan untuk dikomparasi secara visual."""
        if doc_val == recap_val:
            self._lbl_dok.setText(html.escape(doc_val))
            self._lbl_rek.setText(html.escape(recap_val))
        else:
            h_a, h_b = _render_char_diff_html(doc_val, recap_val)
            self._lbl_dok.setText(h_a)
            self._lbl_rek.setText(h_b)
