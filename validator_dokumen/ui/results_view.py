"""
ui/results_view.py - Layar "Hasil" (Master-Detail QSplitter, Tabel Model/View, Detail Diff & Preview PDF).

Fitur:
- StatCards ringkasan di atas (klik = filter status).
- Pencarian dan filter dropdown.
- Model/View: QAbstractTableModel + QSortFilterProxyModel + QTableView.
- Panel kanan (Detail File):
  * StatusBadge besar
  * Kartu "Kenapa hasilnya begini?"
  * Tabel pasangan pencocokan dengan DiffLabel (perbedaan karakter disorot)
  * Pratinjau PDF dengan kotak sorot
  * Tombol override manual status (wajib catatan audit log)
- Tombol Buka Folder Hasil dan Ekspor
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.audit_log import tulis_log_audit
from validator_dokumen.core.models import (
    HasilBulk,
    HasilValidasiDokumen,
    StatusValidasi,
)
from validator_dokumen.ui.diff_label import DiffLabel
from validator_dokumen.ui.pdf_viewer_widget import PdfViewerWidget
from validator_dokumen.ui.theme import COLORS, status_color_pair
from validator_dokumen.ui.widgets.badges import StatusBadge
from validator_dokumen.ui.widgets.buttons import SecondaryButton
from validator_dokumen.ui.widgets.card import Card
from validator_dokumen.ui.widgets.empty_state import EmptyState
from validator_dokumen.ui.widgets.stat_card import StatCard

# ══════════════════════════════════════════════════════════════════════════════
# MODEL TABEL FILE (QAbstractTableModel)
# ══════════════════════════════════════════════════════════════════════════════


class FileTableModel(QAbstractTableModel):
    """
    Model tabel Model/View untuk daftar ribuan file validasi.
    """

    HEADERS: ClassVar[list[str]] = ["Nama File", "Status", "Skor", "Masalah Utama"]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data: list[HasilValidasiDokumen] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._data)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        item = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return item.nama_file
            elif col == 1:
                return item.status.value
            elif col == 2:
                return f"{item.skor}/{item.skor_total}" if item.skor_total > 0 else "-"
            elif col == 3:
                return (
                    item.masalah[0] if item.masalah else (item.error_teknis or "Tidak ada masalah")
                )

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 2:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 1:
                _, bg, _ = status_color_pair(item.status)
                return QColor(bg)

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                txt, _, _ = status_color_pair(item.status)
                return QColor(txt)

        elif role == Qt.ItemDataRole.FontRole:
            if col == 1:
                font = QFont()
                font.setBold(True)
                return font

        elif role == Qt.ItemDataRole.UserRole:
            return item

        return None

    def set_results(self, results: list[HasilValidasiDokumen]) -> None:
        self.beginResetModel()
        self._data = list(results)
        self.endResetModel()

    def append_batch(self, batch: list[HasilValidasiDokumen]) -> None:
        if not batch:
            return
        start = len(self._data)
        end = start + len(batch) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._data.extend(batch)
        self.endInsertRows()

    def get_item(self, row: int) -> HasilValidasiDokumen | None:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def update_item_status(self, row: int, new_status: StatusValidasi) -> None:
        if 0 <= row < len(self._data):
            old = self._data[row]
            # Replace frozen dataclass instance
            import dataclasses

            updated = dataclasses.replace(old, status=new_status)
            self._data[row] = updated
            idx1 = self.index(row, 0)
            idx2 = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(idx1, idx2)


class FileFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy filter untuk tabel file: mendukung filter status dan teks pencarian.
    Secara default menempatkan TIDAK_VALID dan PERLU_DICEK di atas.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filter_status: StatusValidasi | None = None
        self._search_text: str = ""

    def set_status_filter(self, status: StatusValidasi | None) -> None:
        self._filter_status = status
        self.invalidateFilter()

    def set_search_filter(self, text: str) -> None:
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        source_model = self.sourceModel()
        if not isinstance(source_model, FileTableModel):
            return True

        item = source_model.get_item(source_row)
        if not item:
            return False

        # Cek filter status
        if self._filter_status is not None and item.status != self._filter_status:
            return False

        # Cek filter teks pencarian (nama file atau masalah)
        if self._search_text:
            nama_cocok = self._search_text in item.nama_file.lower()
            masalah_cocok = any(self._search_text in m.lower() for m in item.masalah)
            if not (nama_cocok or masalah_cocok):
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802
        """Urutan prioritas default: TIDAK_VALID & PERLU_DICEK di atas."""
        source_model = self.sourceModel()
        if not isinstance(source_model, FileTableModel):
            return super().lessThan(left, right)

        item_a = source_model.get_item(left.row())
        item_b = source_model.get_item(right.row())
        if not item_a or not item_b:
            return super().lessThan(left, right)

        # Bobot urutan status: TIDAK_VALID (1), PERLU_DICEK (2), TIDAK_BISA_DIBACA (3), VALID (4)
        order = {
            StatusValidasi.TIDAK_VALID: 1,
            StatusValidasi.PERLU_DICEK: 2,
            StatusValidasi.TIDAK_BISA_DIBACA: 3,
            StatusValidasi.VALID: 4,
        }
        val_a = order.get(item_a.status, 5)
        val_b = order.get(item_b.status, 5)

        if val_a != val_b:
            return val_a < val_b

        return item_a.nama_file.lower() < item_b.nama_file.lower()


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG OVERRIDE STATUS MANUAL
# ══════════════════════════════════════════════════════════════════════════════


class StatusOverrideDialog(QDialog):
    """
    Dialog pengubahan status manual oleh pengguna dengan catatan wajib.
    """

    def __init__(
        self,
        nama_file: str,
        current_status: StatusValidasi,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Ubah Status: {nama_file}")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel(f"Ubah status untuk file: <b>{nama_file}</b>"))

        row_status = QHBoxLayout()
        row_status.addWidget(QLabel("Status Baru:"))
        self._combo_status = QComboBox()
        for s in StatusValidasi:
            if s != current_status:
                self._combo_status.addItem(s.value, s)
        row_status.addWidget(self._combo_status, stretch=1)
        layout.addLayout(row_status)

        layout.addWidget(QLabel("Catatan Alasan (Wajib diisi):"))
        self._txt_catatan = QTextEdit()
        self._txt_catatan.setPlaceholderText("Tuliskan alasan pengubahan status untuk log audit...")
        self._txt_catatan.setFixedHeight(80)
        layout.addWidget(self._txt_catatan)

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btn_box.accepted.connect(self._validate_and_accept)
        self._btn_box.rejected.connect(self.reject)
        layout.addWidget(self._btn_box)

    def _validate_and_accept(self) -> None:
        if not self._txt_catatan.toPlainText().strip():
            QMessageBox.warning(
                self,
                "Peringatan",
                "Catatan alasan wajib diisi sebelum menyimpan pengubahan status.",
            )
            return
        self.accept()

    def get_selected_status(self) -> StatusValidasi:
        return self._combo_status.currentData()

    def get_catatan(self) -> str:
        return self._txt_catatan.toPlainText().strip()


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS VIEW UTAMA
# ══════════════════════════════════════════════════════════════════════════════


class ResultsView(QWidget):
    """
    Layar 'Hasil' Validasi: Master-Detail Splitter dengan Diff Viewer & PDF Preview.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bulk_result: HasilBulk | None = None
        self._selected_item: HasilValidasiDokumen | None = None
        self._selected_source_row: int = -1

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Baris StatCard Ringkasan di Atas
        row_stats = QHBoxLayout()
        row_stats.setSpacing(12)

        self._stat_valid = StatCard(StatusValidasi.VALID, 0)
        self._stat_valid.clicked.connect(self._on_stat_card_clicked)
        row_stats.addWidget(self._stat_valid)

        self._stat_tidak_valid = StatCard(StatusValidasi.TIDAK_VALID, 0)
        self._stat_tidak_valid.clicked.connect(self._on_stat_card_clicked)
        row_stats.addWidget(self._stat_tidak_valid)

        self._stat_perlu_dicek = StatCard(StatusValidasi.PERLU_DICEK, 0)
        self._stat_perlu_dicek.clicked.connect(self._on_stat_card_clicked)
        row_stats.addWidget(self._stat_perlu_dicek)

        self._stat_tidak_terbaca = StatCard(StatusValidasi.TIDAK_BISA_DIBACA, 0)
        self._stat_tidak_terbaca.clicked.connect(self._on_stat_card_clicked)
        row_stats.addWidget(self._stat_tidak_terbaca)

        main_layout.addLayout(row_stats)

        # 2. Toolbar Filter & Aksi
        row_tools = QHBoxLayout()
        row_tools.setSpacing(10)

        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Cari nama file atau masalah...")
        self._txt_search.setFixedWidth(240)
        self._txt_search.setMinimumHeight(38)
        self._txt_search.textChanged.connect(self._on_search_changed)
        row_tools.addWidget(self._txt_search)

        self._combo_filter = QComboBox()
        self._combo_filter.setMinimumHeight(38)
        self._combo_filter.addItem("Semua Status", None)
        self._combo_filter.addItem("✔ VALID", StatusValidasi.VALID)
        self._combo_filter.addItem("✖ TIDAK VALID", StatusValidasi.TIDAK_VALID)
        self._combo_filter.addItem("⚠ PERLU DICEK", StatusValidasi.PERLU_DICEK)
        self._combo_filter.addItem("⦸ TIDAK BISA DIBACA", StatusValidasi.TIDAK_BISA_DIBACA)
        self._combo_filter.currentIndexChanged.connect(self._on_filter_changed)
        row_tools.addWidget(self._combo_filter)

        row_tools.addStretch()

        self._btn_open_folder = SecondaryButton("Buka Folder Hasil")
        self._btn_open_folder.clicked.connect(self._buka_folder_hasil)
        row_tools.addWidget(self._btn_open_folder)

        main_layout.addLayout(row_tools)

        # 3. Master-Detail Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # KIRI: Tabel File (Model/View)
        self._table_model = FileTableModel(self)
        self._proxy_model = FileFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._table_model)

        self._table_view = QTableView()
        self._table_view.setModel(self._proxy_model)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table_view.setSortingEnabled(True)
        self._table_view.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self._table_view.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table_view.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table_view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table_view.setColumnWidth(0, 180)

        self._table_view.selectionModel().selectionChanged.connect(self._on_table_selection_changed)
        self._splitter.addWidget(self._table_view)

        # KANAN: Detail File Terpilih
        self._detail_container = QWidget()
        detail_layout = QVBoxLayout(self._detail_container)
        detail_layout.setContentsMargins(12, 0, 0, 0)
        detail_layout.setSpacing(12)

        # Panel Kosong (Empty state jika belum ada file dipilih)
        self._empty_detail = EmptyState(
            icon_text="📄",
            title="Pilih File Dokumen",
            description="Pilih salah satu baris file pada tabel di kiri untuk melihat rincian keputusan validasi dan pratinjau dokumen.",
        )
        detail_layout.addWidget(self._empty_detail)

        # Panel Isi Detail (Scrollable)
        self._content_scroll = QScrollArea()
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        # Header Detail: Nama File + StatusBadge + Tombol Ubah Status
        self._card_header = Card()
        hdr_layout = QHBoxLayout()
        self._lbl_detail_filename = QLabel("nama_dokumen.pdf")
        self._lbl_detail_filename.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {COLORS.text_primary};"
        )
        hdr_layout.addWidget(self._lbl_detail_filename, stretch=1)

        self._detail_badge = StatusBadge(StatusValidasi.VALID, large=True)
        hdr_layout.addWidget(self._detail_badge)

        self._btn_override_status = SecondaryButton("Ubah Status...")
        self._btn_override_status.clicked.connect(self._show_override_dialog)
        hdr_layout.addWidget(self._btn_override_status)
        self._card_header.layout().addLayout(hdr_layout)
        self._content_layout.addWidget(self._card_header)

        # Kartu "Kenapa hasilnya begini?" (Jejak Masalah)
        self._card_reason = Card()
        self._lbl_reason_title = QLabel("Kenapa hasilnya begini?")
        self._lbl_reason_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {COLORS.text_primary};"
        )
        self._card_reason.layout().addWidget(self._lbl_reason_title)

        self._lbl_reason_desc = QLabel()
        self._lbl_reason_desc.setWordWrap(True)
        self._lbl_reason_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.text_secondary};")
        self._card_reason.layout().addWidget(self._lbl_reason_desc)
        self._content_layout.addWidget(self._card_reason)

        # Kartu Tabel Pasangan & Karakter Diff
        self._card_pairs = Card()
        lbl_pairs_title = QLabel("Hasil Pencocokan Kolom Rekapan <-> Field Dokumen")
        lbl_pairs_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {COLORS.text_primary};"
        )
        self._card_pairs.layout().addWidget(lbl_pairs_title)

        self._pairs_container = QVBoxLayout()
        self._pairs_container.setSpacing(10)
        self._card_pairs.layout().addLayout(self._pairs_container)
        self._content_layout.addWidget(self._card_pairs)

        # Kartu Pratinjau Halaman Dokumen PDF
        self._card_pdf = Card()
        lbl_pdf_title = QLabel("Pratinjau Dokumen")
        lbl_pdf_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {COLORS.text_primary};"
        )
        self._card_pdf.layout().addWidget(lbl_pdf_title)

        self._pdf_viewer = PdfViewerWidget()
        self._pdf_viewer.setFixedHeight(350)
        self._card_pdf.layout().addWidget(self._pdf_viewer)
        self._content_layout.addWidget(self._card_pdf)

        self._content_scroll.setWidget(self._content_widget)
        self._content_scroll.hide()
        detail_layout.addWidget(self._content_scroll)

        self._splitter.addWidget(self._detail_container)
        self._splitter.setSizes([450, 650])
        main_layout.addWidget(self._splitter, stretch=1)

    def display_bulk_results(self, bulk_result: HasilBulk) -> None:
        """Tampilkan seluruh data hasil bulk."""
        self._bulk_result = bulk_result

        # Update StatCard
        self._stat_valid.set_count(bulk_result.valid)
        self._stat_tidak_valid.set_count(bulk_result.tidak_valid)
        self._stat_perlu_dicek.set_count(bulk_result.perlu_dicek)
        self._stat_tidak_terbaca.set_count(bulk_result.tidak_bisa_dibaca)

        # Set model
        self._table_model.set_results(list(bulk_result.hasil_per_file))

        # Pilih baris pertama jika ada
        if self._proxy_model.rowCount() > 0:
            self._table_view.selectRow(0)

    def _on_stat_card_clicked(self, status: StatusValidasi) -> None:
        """Filter saat StatCard diklik."""
        curr = self._combo_filter.currentData()
        if curr == status:
            self._combo_filter.setCurrentIndex(0)  # Reset ke semua
        else:
            # Set ke status ini
            for i in range(self._combo_filter.count()):
                if self._combo_filter.itemData(i) == status:
                    self._combo_filter.setCurrentIndex(i)
                    break

    def _on_filter_changed(self) -> None:
        status = self._combo_filter.currentData()
        self._proxy_model.set_status_filter(status)
        self._update_stat_cards_active(status)

    def _update_stat_cards_active(self, active_status: StatusValidasi | None) -> None:
        self._stat_valid.set_active(active_status == StatusValidasi.VALID)
        self._stat_tidak_valid.set_active(active_status == StatusValidasi.TIDAK_VALID)
        self._stat_perlu_dicek.set_active(active_status == StatusValidasi.PERLU_DICEK)
        self._stat_tidak_terbaca.set_active(active_status == StatusValidasi.TIDAK_BISA_DIBACA)

    def _on_search_changed(self, text: str) -> None:
        self._proxy_model.set_search_filter(text)

    def _on_table_selection_changed(self) -> None:
        indexes = self._table_view.selectionModel().selectedRows()
        if not indexes:
            self._content_scroll.hide()
            self._empty_detail.show()
            self._selected_item = None
            self._selected_source_row = -1
            return

        proxy_idx = indexes[0]
        source_idx = self._proxy_model.mapToSource(proxy_idx)
        self._selected_source_row = source_idx.row()
        item = self._table_model.get_item(self._selected_source_row)

        if not item:
            return

        self._selected_item = item
        self._render_detail(item)

    def _render_detail(self, item: HasilValidasiDokumen) -> None:
        """Tampilkan rincian file terpilih."""
        self._empty_detail.hide()
        self._content_scroll.show()

        self._lbl_detail_filename.setText(item.nama_file)
        self._detail_badge.set_status(item.status)

        # Rincian alasan
        reasons_text = []
        if item.skema_terpakai:
            reasons_text.append(
                f"• Skema terpakai: <b>{item.skema_terpakai}</b> (Skor: {item.skor}/{item.skor_total})"
            )
        if item.baris_rekap_nomor:
            reasons_text.append(
                f"• Baris rekapan acuan: {item.file_rekap}, sheet '{item.sheet_rekap}', baris {item.baris_rekap_nomor}"
            )
        for m in item.masalah:
            reasons_text.append(f"• {m}")
        if item.error_teknis:
            reasons_text.append(f"• Error teknis: {item.error_teknis}")

        self._lbl_reason_desc.setText(
            "<br>".join(reasons_text)
            if reasons_text
            else "Semua pasangan cocok dan memenuhi aturan."
        )

        # Bersihkan pasangan lama
        while self._pairs_container.count() > 0:
            child = self._pairs_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Render pasangan
        ada_pasangan = False
        for hs in item.hasil_skema:
            if hs.baris_rekap_id:
                for hp in hs.pasangan_hasil:
                    ada_pasangan = True
                    pair_box = QWidget()
                    pair_layout = QVBoxLayout(pair_box)
                    pair_layout.setContentsMargins(8, 6, 8, 6)
                    pair_layout.setSpacing(4)
                    pair_box.setStyleSheet(
                        f"background-color: {COLORS.bg_app}; border-radius: 6px;"
                    )

                    title_row = QHBoxLayout()
                    lbl_field_title = QLabel(f"<b>[{hp.field_dokumen}]</b> <-> [{hp.kolom_rekap}]")
                    lbl_field_title.setStyleSheet("font-size: 12px;")
                    title_row.addWidget(lbl_field_title)
                    title_row.addStretch()

                    # Indikator Cocok/Tidak
                    lbl_ok = QLabel("✔ Cocok" if hp.cocok else "✖ Beda")
                    lbl_ok.setStyleSheet(
                        f"font-weight: 700; color: {COLORS.valid_text if hp.cocok else COLORS.tidak_valid_text};"
                    )
                    title_row.addWidget(lbl_ok)
                    pair_layout.addLayout(title_row)

                    # Diff visual
                    diff = DiffLabel()
                    diff.set_values(hp.nilai_dokumen, hp.nilai_rekap)
                    pair_layout.addWidget(diff)

                    self._pairs_container.addWidget(pair_box)

        self._card_pairs.setVisible(ada_pasangan)

        # Muat pratinjau PDF
        if Path(item.path_file).exists():
            self._card_pdf.show()
            self._pdf_viewer.load_document(item.path_file, page_num=0)
        else:
            self._card_pdf.hide()

    def _show_override_dialog(self) -> None:
        """Tampilkan dialog pengubahan status manual."""
        if not self._selected_item or self._selected_source_row < 0:
            return

        dlg = StatusOverrideDialog(self._selected_item.nama_file, self._selected_item.status, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_status = dlg.get_selected_status()
            catatan = dlg.get_catatan()

            # Catat ke log audit jika output folder ada
            if self._bulk_result:
                folder_out = Path(self._bulk_result.folder_output)
                if not folder_out.is_absolute():
                    # Ambil dari parent path file
                    parent_input = Path(self._selected_item.path_file).parent
                    folder_out = parent_input.parent / self._bulk_result.folder_output
                with contextlib.suppress(Exception):
                    tulis_log_audit(
                        folder_output=folder_out,
                        nama_file=self._selected_item.nama_file,
                        status_lama=self._selected_item.status,
                        status_baru=new_status,
                        catatan=catatan,
                    )

            # Update di tabel model
            self._table_model.update_item_status(self._selected_source_row, new_status)
            self._selected_item = self._table_model.get_item(self._selected_source_row)
            if self._selected_item:
                self._render_detail(self._selected_item)

            QMessageBox.information(
                self,
                "Status Diperbarui",
                f"Status file '{self._selected_item.nama_file}' telah diubah menjadi {new_status.value} dan dicatat di log audit.",
            )

    def _buka_folder_hasil(self) -> None:
        """Buka folder hasil validasi di Windows Explorer."""
        if not self._bulk_result:
            QMessageBox.information(self, "Informasi", "Belum ada hasil validasi bulk yang aktif.")
            return

        folder_str = self._bulk_result.folder_output
        target_path = Path(folder_str)
        if not target_path.is_absolute():
            # Cari di samping lokasi file pertama
            if self._bulk_result.hasil_per_file:
                first_file = Path(self._bulk_result.hasil_per_file[0].path_file)
                target_path = first_file.parent.parent / folder_str

        if target_path.exists():
            subprocess.Popen(f'explorer "{target_path}"')
        else:
            QMessageBox.warning(
                self, "Peringatan", f"Folder hasil belum ditemukan di: {target_path}"
            )
