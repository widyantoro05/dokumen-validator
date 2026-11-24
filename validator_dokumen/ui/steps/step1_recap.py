"""
ui/steps/step1_recap.py - Langkah 1: Muat & Analisis Rekapan Acuan.

Pengguna memilih berkas Excel atau PDF tabel, memilih sheet (jika Excel),
menentukan baris header, mempratinjau isi tabel dengan QTableView, dan
melihat statistik kualitas kolom secara dinamis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import openpyxl
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.models import TabelRekap
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.card import Card
from validator_dokumen.ui.widgets.info_banner import InfoBanner
from validator_dokumen.ui.widgets.labeled_field import LabeledField
from validator_dokumen.ui.widgets.section_header import SectionHeader


class RecapTableModel(QAbstractTableModel):
    """Model tabel dinamis untuk pratinjau isi tabel rekapan."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._headers: list[str] = []
        self._rows: list[dict[str, str]] = []

    def set_data(self, headers: list[str], rows: list[dict[str, str]]) -> None:
        self.beginResetModel()
        self._headers = list(headers)
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._headers)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        elif orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            col_name = self._headers[index.column()]
            return self._rows[index.row()].get(col_name, "")
        return None


class ColumnStatsTableModel(QAbstractTableModel):
    """Model tabel untuk statistik kualitas setiap kolom rekapan."""

    HEADERS: ClassVar[list[str]] = ["Nama Kolom", "Terisi", "Kosong", "Nilai Unik", "Persen Unik"]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stats: list[dict[str, Any]] = []

    def set_stats(self, stats: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._stats = list(stats)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._stats)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._stats)):
            return None

        item = self._stats[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return item["nama"]
            elif col == 1:
                return f"{item['terisi']:,}"
            elif col == 2:
                return f"{item['kosong']:,}"
            elif col == 3:
                return f"{item['unik']:,}"
            elif col == 4:
                return f"{item['persen_unik']:.1f}%"
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col > 0:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class Step1Recap(QWidget):
    """Layar Langkah 1: Muat & Analisis Rekapan Acuan."""

    # Sinyal saat rekapan berhasil dimuat (TabelRekap, path)
    recap_loaded = Signal(object, str)

    def __init__(self, recap_service: RecapService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rs = recap_service
        self._tabel_rekap: TabelRekap | None = None
        self._recap_path: str = ""

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Langkah
        header = SectionHeader(
            title="Langkah 1: Muat Dokumen Acuan (Rekapan)",
            subtitle="Pilih berkas Excel (.xlsx) atau PDF tabel sebagai data acuan pembanding dokumen izin. "
            "Semua kolom dibaca dinamis apa adanya.",
        )
        main_layout.addWidget(header)

        # Banner Info/Error
        self._banner = InfoBanner("", "info")
        self._banner.setVisible(False)
        main_layout.addWidget(self._banner)

        # Card Konfigurasi Berkas
        cfg_card = Card()
        cfg_layout = QVBoxLayout()
        cfg_layout.setSpacing(14)

        # Baris Pemilihan Berkas dengan LabeledField
        w_file = QWidget()
        row_file = QHBoxLayout(w_file)
        row_file.setContentsMargins(0, 0, 0, 0)
        row_file.setSpacing(8)

        self._edit_path = QLineEdit()
        self._edit_path.setMinimumHeight(38)
        self._edit_path.setPlaceholderText("Pilih berkas Excel (.xlsx) atau PDF tabel...")
        self._edit_path.setReadOnly(True)
        row_file.addWidget(self._edit_path, stretch=1)

        btn_browse = SecondaryButton("Pilih Berkas...")
        btn_browse.setMinimumHeight(38)
        btn_browse.clicked.connect(self._browse_recap)
        row_file.addWidget(btn_browse)

        field_file = LabeledField("Berkas Rekapan Acuan", w_file, required=True)
        cfg_layout.addWidget(field_file)

        # Opsi Lanjutan: Sheet & Baris Header & Tombol Muat
        row_options = QHBoxLayout()
        row_options.setSpacing(16)

        self._combo_sheet = QComboBox()
        self._combo_sheet.setEnabled(False)
        self._combo_sheet.setMinimumHeight(38)
        field_sheet = LabeledField("Sheet Excel", self._combo_sheet)
        row_options.addWidget(field_sheet, stretch=2)

        self._spin_header = QSpinBox()
        self._spin_header.setRange(1, 100)
        self._spin_header.setValue(1)
        self._spin_header.setMinimumHeight(38)
        field_header = LabeledField("Baris Header (Nomor Baris)", self._spin_header)
        row_options.addWidget(field_header, stretch=1)

        self._btn_load = PrimaryButton("Muat Tabel Rekapan")
        self._btn_load.setMinimumHeight(38)
        self._btn_load.clicked.connect(self._muat_rekap)
        field_load = LabeledField("Aksi", self._btn_load)
        row_options.addWidget(field_load, stretch=1)

        cfg_layout.addLayout(row_options)
        cfg_card.layout().addLayout(cfg_layout)
        main_layout.addWidget(cfg_card)

        # Area Pratinjau & Statistik (Splitter)
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # Panel Atas: Pratinjau Tabel
        panel_preview = QFrame()
        layout_preview = QVBoxLayout(panel_preview)
        layout_preview.setContentsMargins(0, 0, 0, 0)
        layout_preview.setSpacing(8)

        lbl_preview_title = QLabel("Pratinjau Isi Rekapan (Maksimal 100 Baris Pertama)")
        lbl_preview_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {COLORS.text_primary};"
        )
        layout_preview.addWidget(lbl_preview_title)

        self._table_model = RecapTableModel(self)
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        layout_preview.addWidget(self._table_view)

        self._splitter.addWidget(panel_preview)

        # Panel Bawah: Statistik Kualitas Kolom
        panel_stats = QFrame()
        layout_stats = QVBoxLayout(panel_stats)
        layout_stats.setContentsMargins(0, 8, 0, 0)
        layout_stats.setSpacing(8)

        lbl_stats_title = QLabel("Statistik Kualitas Kolom (Analisis Keseluruhan Baris)")
        lbl_stats_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {COLORS.text_primary};"
        )
        layout_stats.addWidget(lbl_stats_title)

        self._stats_model = ColumnStatsTableModel(self)
        self._stats_view = QTableView()
        self._stats_view.setModel(self._stats_model)
        self._stats_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._stats_view.horizontalHeader().setStretchLastSection(True)
        self._stats_view.setAlternatingRowColors(True)
        self._stats_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        layout_stats.addWidget(self._stats_view)

        self._splitter.addWidget(panel_stats)
        self._splitter.setSizes([260, 160])

        main_layout.addWidget(self._splitter, stretch=1)

    def _browse_recap(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih Berkas Rekapan Acuan",
            "",
            "Berkas Data (*.xlsx *.xls *.pdf);;Excel (*.xlsx *.xls);;PDF Tabel (*.pdf)",
        )
        if not path:
            return

        self._edit_path.setText(path)
        p = Path(path)

        # Periksa sheet jika berkas adalah Excel
        if p.suffix.lower() in [".xlsx", ".xls"]:
            self._combo_sheet.clear()
            try:
                wb = openpyxl.load_workbook(path, read_only=True)
                for s in wb.sheetnames:
                    self._combo_sheet.addItem(s)
                wb.close()
                self._combo_sheet.setEnabled(True)
            except Exception:
                self._combo_sheet.addItem("Sheet1")
                self._combo_sheet.setEnabled(False)
        else:
            self._combo_sheet.clear()
            self._combo_sheet.addItem("(Bukan Excel)")
            self._combo_sheet.setEnabled(False)

        # Muat otomatis
        self._muat_rekap()

    def _muat_rekap(self) -> None:
        path_str = self._edit_path.text().strip()
        if not path_str:
            self._tampilkan_banner("Silakan pilih berkas rekapan terlebih dahulu.", "warning")
            return

        p = Path(path_str)
        if not p.is_file():
            self._tampilkan_banner(f"Berkas tidak ditemukan: {path_str}", "error")
            return

        sheet = self._combo_sheet.currentText() if self._combo_sheet.isEnabled() else None
        baris_hdr = self._spin_header.value()

        try:
            tabel = self._rs.muat_tabel_rekap(p, sheet_name=sheet, baris_header=baris_hdr)
            self._tabel_rekap = tabel
            self._recap_path = path_str

            # Update preview tabel (maks 100 baris)
            preview_rows = [b.data for b in tabel.baris[:100]]
            self._table_model.set_data(list(tabel.kolom), preview_rows)

            # Analisis statistik kolom
            stats = self._hitung_statistik_kolom(tabel)
            self._stats_model.set_stats(stats)

            self._tampilkan_banner(
                f"Tabel berhasil dimuat: {len(tabel.baris):,} baris dan {len(tabel.kolom)} kolom terdeteksi.",
                "success",
            )

            # Pancarkan sinyal
            self.recap_loaded.emit(tabel, path_str)

        except Exception as e:
            self._tampilkan_banner(f"Gagal memuat tabel rekapan: {e}", "error")

    def _hitung_statistik_kolom(self, tabel: TabelRekap) -> list[dict[str, Any]]:
        hasil = []
        for col in tabel.kolom:
            terisi = 0
            kosong = 0
            nilai_set: set[str] = set()

            for b in tabel.baris:
                val = b.data.get(col, "").strip()
                if val:
                    terisi += 1
                    nilai_set.add(val)
                else:
                    kosong += 1

            persen_unik = (len(nilai_set) / terisi * 100.0) if terisi > 0 else 0.0
            hasil.append(
                {
                    "nama": col,
                    "terisi": terisi,
                    "kosong": kosong,
                    "unik": len(nilai_set),
                    "persen_unik": persen_unik,
                }
            )
        return hasil

    def _tampilkan_banner(self, pesan: str, tipe: str) -> None:
        self._banner.set_state(pesan, tipe)
        self._banner.setVisible(True)

    def dapatkan_tabel_rekap(self) -> TabelRekap | None:
        return self._tabel_rekap

    def dapatkan_path_rekap(self) -> str:
        return self._recap_path

    def is_valid_step(self) -> bool:
        """Langkah 1 valid jika tabel rekapan sudah dimuat dan punya baris."""
        return self._tabel_rekap is not None and len(self._tabel_rekap.baris) > 0
