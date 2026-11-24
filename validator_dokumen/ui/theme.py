"""
ui/theme.py - Token Desain dan Gaya UI Validator Dokumen.

Satu-satunya sumber kebenaran untuk warna, tipografi, radius, spasi,
dan stylesheet aplikasi. Tidak boleh ada hardcode warna di tempat lain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from validator_dokumen.core.models import StatusValidasi


@dataclass(frozen=True)
class ThemeColors:
    # Latar Belakang & Permukaan
    bg_app: str = "#F5F7FA"
    bg_card: str = "#FFFFFF"
    bg_sidebar: str = "#0F172A"
    bg_sidebar_hover: str = "#1E293B"
    bg_sidebar_active: str = "#2563EB"
    bg_input: str = "#FFFFFF"
    bg_hover: str = "#F1F5F9"
    bg_selected: str = "#EFF6FF"

    # Border
    border: str = "#E2E8F0"
    border_focus: str = "#2563EB"
    border_subtle: str = "#CBD5E1"

    # Teks
    text_primary: str = "#1E293B"
    text_secondary: str = "#64748B"
    text_muted: str = "#94A3B8"
    text_white: str = "#FFFFFF"

    # Aksen & Interaksi
    accent: str = "#2563EB"
    accent_hover: str = "#1D4ED8"
    accent_pressed: str = "#1E40AF"

    # Status Validasi
    valid_text: str = "#166534"
    valid_bg: str = "#DCFCE7"
    valid_border: str = "#86EFAC"

    tidak_valid_text: str = "#991B1B"
    tidak_valid_bg: str = "#FEE2E2"
    tidak_valid_border: str = "#FCA5A5"

    perlu_dicek_text: str = "#92400E"
    perlu_dicek_bg: str = "#FEF3C7"
    perlu_dicek_border: str = "#FCD34D"

    tidak_terbaca_text: str = "#475569"
    tidak_terbaca_bg: str = "#E2E8F0"
    tidak_terbaca_border: str = "#CBD5E1"

    # Diff visual
    diff_added_bg: str = "#DCFCE7"
    diff_added_text: str = "#166534"
    diff_removed_bg: str = "#FEE2E2"
    diff_removed_text: str = "#991B1B"


COLORS: Final[ThemeColors] = ThemeColors()


def status_color_pair(status: StatusValidasi) -> tuple[str, str, str]:
    """
    Mengembalikan tuple (text_color, bg_color, border_color) untuk StatusValidasi.
    """
    if status == StatusValidasi.VALID:
        return COLORS.valid_text, COLORS.valid_bg, COLORS.valid_border
    if status == StatusValidasi.TIDAK_VALID:
        return COLORS.tidak_valid_text, COLORS.tidak_valid_bg, COLORS.tidak_valid_border
    if status == StatusValidasi.PERLU_DICEK:
        return COLORS.perlu_dicek_text, COLORS.perlu_dicek_bg, COLORS.perlu_dicek_border
    return COLORS.tidak_terbaca_text, COLORS.tidak_terbaca_bg, COLORS.tidak_terbaca_border


def status_icon_and_label(status: StatusValidasi) -> tuple[str, str]:
    """
    Mengembalikan simbol dan label teks baku untuk StatusValidasi.
    """
    if status == StatusValidasi.VALID:
        return "✔", "VALID"
    if status == StatusValidasi.TIDAK_VALID:
        return "✖", "TIDAK VALID"
    if status == StatusValidasi.PERLU_DICEK:
        return "⚠", "PERLU DICEK"
    return "⦸", "TIDAK BISA DIBACA"


def generate_qss() -> str:
    """
    Membangkitkan stylesheet QSS global dari token desain tema.
    """
    return f"""
    /* Global Base */
    QWidget {{
        font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        font-size: 13px;
        color: {COLORS.text_primary};
        background-color: transparent;
    }}

    QMainWindow, QDialog {{
        background-color: {COLORS.bg_app};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {COLORS.bg_app};
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS.border_subtle};
        min-height: 24px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLORS.text_muted};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: {COLORS.bg_app};
        height: 10px;
        margin: 0px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLORS.border_subtle};
        min-width: 24px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {COLORS.text_muted};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* Input Controls */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {COLORS.bg_input};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        padding: 6px 10px;
        min-height: 24px;
        font-size: 13px;
        color: {COLORS.text_primary};
        selection-background-color: {COLORS.accent};
        selection-color: {COLORS.text_white};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1.5px solid {COLORS.border_focus};
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        background-color: {COLORS.bg_app};
        color: {COLORS.text_muted};
    }}

    /* ComboBox dropdown */
    QComboBox {{
        padding-right: 26px;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 26px;
        border-left: 1px solid {COLORS.border};
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }}
    QComboBox::down-arrow {{
        width: 10px;
        height: 10px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS.bg_card};
        border: 1px solid {COLORS.border};
        border-radius: 6px;
        selection-background-color: {COLORS.bg_selected};
        selection-color: {COLORS.accent};
        padding: 4px;
    }}

    /* Tables (Model/View) */
    QTableView {{
        background-color: {COLORS.bg_card};
        border: 1px solid {COLORS.border};
        border-radius: 8px;
        gridline-color: {COLORS.border};
        selection-background-color: {COLORS.bg_selected};
        selection-color: {COLORS.text_primary};
        outline: none;
    }}
    QTableView::item {{
        padding: 6px 10px;
        min-height: 36px;
        border-bottom: 1px solid {COLORS.bg_app};
    }}
    QTableView::item:hover {{
        background-color: {COLORS.bg_hover};
    }}
    QTableView::item:selected {{
        background-color: {COLORS.bg_selected};
        color: {COLORS.accent};
    }}
    QHeaderView::section {{
        background-color: #F8FAFC;
        color: {COLORS.text_secondary};
        font-weight: 600;
        padding: 8px 10px;
        border: none;
        border-bottom: 2px solid {COLORS.border};
    }}

    /* Splitters */
    QSplitter::handle {{
        background-color: {COLORS.border};
    }}
    QSplitter::handle:horizontal {{
        width: 3px;
    }}
    QSplitter::handle:vertical {{
        height: 3px;
    }}

    /* CheckBoxes & RadioButtons */
    QCheckBox, QRadioButton {{
        spacing: 8px;
        color: {COLORS.text_primary};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {COLORS.border_subtle};
        border-radius: 4px;
        background: {COLORS.bg_input};
    }}
    QRadioButton::indicator {{
        border-radius: 9px;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {COLORS.accent};
        border-color: {COLORS.accent};
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {COLORS.bg_sidebar};
        color: {COLORS.text_white};
        border: none;
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* Progress Bar */
    QProgressBar {{
        background-color: {COLORS.border};
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {COLORS.accent};
        border-radius: 4px;
    }}
    """
