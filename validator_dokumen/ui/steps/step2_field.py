"""
ui/steps/step2_field.py - Langkah 2: Muat Dokumen Contoh & Definisikan Field.

Pengguna memuat contoh dokumen PDF izin, melihat pratinjau halaman PDF,
mendefinisikan field dokumen secara dinamis (berdasarkan label, regex, atau koordinat),
dan langsung menguji ekstraksi teks untuk memverifikasi nilai yang diambil.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.field_extractor import ekstrak_semua_field
from validator_dokumen.core.models import DefinisiField, NilaiField
from validator_dokumen.core.pdf_reader import baca_pdf
from validator_dokumen.ui.pdf_viewer_widget import PdfViewerWidget
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import DangerButton, PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.info_banner import InfoBanner
from validator_dokumen.ui.widgets.section_header import SectionHeader


class FieldTableModel(QAbstractTableModel):
    """Model tabel untuk daftar field dokumen yang didefinisikan pengguna."""

    HEADERS: ClassVar[list[str]] = [
        "Nama Field",
        "Cara Ambil",
        "Wajib",
        "Nilai Hasil Uji",
        "Confidence",
    ]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fields: list[DefinisiField] = []
        self._nilai_uji: dict[str, NilaiField] = {}

    def set_fields(
        self, fields: list[DefinisiField], nilai_uji: dict[str, NilaiField] | None = None
    ) -> None:
        self.beginResetModel()
        self._fields = list(fields)
        if nilai_uji is not None:
            self._nilai_uji = dict(nilai_uji)
        self.endResetModel()

    def set_nilai_uji(self, nilai_uji: dict[str, NilaiField]) -> None:
        self.beginResetModel()
        self._nilai_uji = dict(nilai_uji)
        self.endResetModel()

    def get_field(self, index: int) -> DefinisiField | None:
        if 0 <= index < len(self._fields):
            return self._fields[index]
        return None

    def get_all_fields(self) -> list[DefinisiField]:
        return list(self._fields)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._fields)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._fields)):
            return None

        field = self._fields[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return field.nama
            elif col == 1:
                return field.cara_ambil.upper()
            elif col == 2:
                return "Ya" if field.wajib else "Tidak"
            elif col == 3:
                nf = self._nilai_uji.get(field.nama)
                if nf is not None:
                    return nf.nilai_mentah if nf.nilai_mentah else "(Kosong)"
                return "-"
            elif col == 4:
                nf = self._nilai_uji.get(field.nama)
                if nf is not None:
                    return f"{nf.confidence:.0f}%"
                return "-"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [1, 2, 4]:
                return int(Qt.AlignmentFlag.AlignCenter)
        return None


class FieldDialog(QDialog):
    """Dialog untuk menambah atau mengubah DefinisiField."""

    def __init__(
        self, field: DefinisiField | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tambah Definisi Field" if not field else "Ubah Definisi Field")
        self.resize(500, 420)
        self._existing_field = field

        self._setup_ui()
        if field:
            self._load_from_field(field)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        # Nama Field
        self._edit_nama = QLineEdit()
        self._edit_nama.setPlaceholderText("Contoh: nomor_izin, nama_perusahaan, tanggal_terbit")
        form.addRow("<b>Nama Field:</b>", self._edit_nama)

        # Cara Ambil
        self._combo_cara = QComboBox()
        self._combo_cara.addItem("Label (Ambil teks setelah kata kunci label)", "label")
        self._combo_cara.addItem("Pola Regex (Regular Expression)", "pola")
        self._combo_cara.addItem("Area Koordinat (Halaman & Bounding Box)", "area")
        self._combo_cara.currentIndexChanged.connect(self._on_cara_changed)
        form.addRow("<b>Cara Ekstraksi:</b>", self._combo_cara)

        # Panel Parameter Spesifik
        self._lbl_param_help = QLabel()
        self._lbl_param_help.setWordWrap(True)
        self._lbl_param_help.setStyleSheet(f"color: {COLORS.text_secondary}; font-size: 11px;")

        # Param: Label
        self._widget_label = QWidget()
        l_layout = QVBoxLayout(self._widget_label)
        l_layout.setContentsMargins(0, 0, 0, 0)
        self._edit_labels = QLineEdit()
        self._edit_labels.setPlaceholderText("Kata kunci dipisah koma, contoh: Nomor Izin, No. Izin, No:")
        l_layout.addWidget(QLabel("Kata Kunci / Label:"))
        l_layout.addWidget(self._edit_labels)

        # Param: Pola Regex
        self._widget_pola = QWidget()
        p_layout = QVBoxLayout(self._widget_pola)
        p_layout.setContentsMargins(0, 0, 0, 0)
        self._edit_regex = QLineEdit()
        self._edit_regex.setPlaceholderText(r"Contoh: Nomor\s*:\s*([A-Za-z0-9\/\-]+)")
        p_layout.addWidget(QLabel("Pola Regex (Grup tangkapan dalam kurung):"))
        p_layout.addWidget(self._edit_regex)

        # Param: Area Koordinat
        self._widget_area = QWidget()
        a_layout = QFormLayout(self._widget_area)
        a_layout.setContentsMargins(0, 0, 0, 0)
        self._spin_page = QSpinBox()
        self._spin_page.setRange(1, 100)
        self._spin_page.setValue(1)
        a_layout.addRow("Halaman:", self._spin_page)

        box_coords = QHBoxLayout()
        self._spin_x0 = QSpinBox()
        self._spin_x0.setRange(0, 2000)
        self._spin_y0 = QSpinBox()
        self._spin_y0.setRange(0, 2000)
        self._spin_x1 = QSpinBox()
        self._spin_x1.setRange(0, 2000)
        self._spin_x1.setValue(300)
        self._spin_y1 = QSpinBox()
        self._spin_y1.setRange(0, 2000)
        self._spin_y1.setValue(50)
        box_coords.addWidget(QLabel("x0:"))
        box_coords.addWidget(self._spin_x0)
        box_coords.addWidget(QLabel("y0:"))
        box_coords.addWidget(self._spin_y0)
        box_coords.addWidget(QLabel("x1:"))
        box_coords.addWidget(self._spin_x1)
        box_coords.addWidget(QLabel("y1:"))
        box_coords.addWidget(self._spin_y1)
        a_layout.addRow("Koordinat (pt):", box_coords)

        form.addRow(self._widget_label)
        form.addRow(self._widget_pola)
        form.addRow(self._widget_area)

        # Opsi Wajib Ada
        self._chk_wajib = QCheckBox("Wajib Ada (Tandai TIDAK VALID jika field ini tidak ditemukan)")
        form.addRow("", self._chk_wajib)

        # Deskripsi
        self._edit_deskripsi = QLineEdit()
        self._edit_deskripsi.setPlaceholderText("Deskripsi opsional field ini")
        form.addRow("Deskripsi:", self._edit_deskripsi)

        layout.addLayout(form)

        # Tombol Aksi Dialog
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._on_cara_changed(0)

    def _on_cara_changed(self, index: int) -> None:
        cara = self._combo_cara.currentData()
        self._widget_label.setVisible(cara == "label")
        self._widget_pola.setVisible(cara == "pola")
        self._widget_area.setVisible(cara == "area")

    def _load_from_field(self, field: DefinisiField) -> None:
        self._edit_nama.setText(field.nama)
        idx = self._combo_cara.findData(field.cara_ambil)
        if idx >= 0:
            self._combo_cara.setCurrentIndex(idx)
        self._chk_wajib.setChecked(field.wajib)
        self._edit_deskripsi.setText(field.deskripsi)

        param = field.parameter
        if field.cara_ambil == "label":
            labels = param.get("label", [])
            if isinstance(labels, list):
                self._edit_labels.setText(", ".join(labels))
            else:
                self._edit_labels.setText(str(labels))
        elif field.cara_ambil == "pola":
            self._edit_regex.setText(param.get("pola", ""))
        elif field.cara_ambil == "area":
            self._spin_page.setValue(param.get("halaman", 1))
            kotak = param.get("kotak", [0, 0, 300, 50])
            if len(kotak) == 4:
                self._spin_x0.setValue(int(kotak[0]))
                self._spin_y0.setValue(int(kotak[1]))
                self._spin_x1.setValue(int(kotak[2]))
                self._spin_y1.setValue(int(kotak[3]))

    def _validate_and_accept(self) -> None:
        nama = self._edit_nama.text().strip()
        if not nama:
            QMessageBox.warning(self, "Peringatan", "Nama field tidak boleh kosong.")
            return

        cara = self._combo_cara.currentData()
        if cara == "label" and not self._edit_labels.text().strip():
            QMessageBox.warning(self, "Peringatan", "Silakan masukkan setidaknya satu kata kunci label.")
            return
        elif cara == "pola" and not self._edit_regex.text().strip():
            QMessageBox.warning(self, "Peringatan", "Silakan masukkan pola regex yang valid.")
            return

        self.accept()

    def get_definisi_field(self) -> DefinisiField:
        nama = self._edit_nama.text().strip()
        cara = str(self._combo_cara.currentData())
        wajib = self._chk_wajib.isChecked()
        deskripsi = self._edit_deskripsi.text().strip()
        param: dict[str, Any] = {}

        if cara == "label":
            raw_labels = self._edit_labels.text().split(",")
            param["label"] = [lbl.strip() for lbl in raw_labels if lbl.strip()]
        elif cara == "pola":
            param["pola"] = self._edit_regex.text().strip()
            param["grup"] = 1
        elif cara == "area":
            param["halaman"] = self._spin_page.value()
            param["kotak"] = [
                self._spin_x0.value(),
                self._spin_y0.value(),
                self._spin_x1.value(),
                self._spin_y1.value(),
            ]

        field_id = self._existing_field.id if self._existing_field else str(uuid.uuid4())
        return DefinisiField(
            id=field_id,
            nama=nama,
            cara_ambil=cara,
            parameter=param,
            wajib=wajib,
            deskripsi=deskripsi,
        )


class Step2Field(QWidget):
    """Layar Langkah 2: Muat Dokumen Contoh & Definisikan Field."""

    # Sinyal saat field diperbarui (list[DefinisiField], list[str] pdf_paths)
    fields_updated = Signal(list, list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pdf_paths: list[str] = []
        self._fields: list[DefinisiField] = []
        self._nilai_uji: dict[str, NilaiField] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header Langkah
        header = SectionHeader(
            title="Langkah 2: Muat Contoh Dokumen & Definisikan Field",
            subtitle="Muat satu atau beberapa contoh berkas PDF izin, lalu tentukan field-field apa saja "
            "yang perlu diekstrak untuk dicocokkan dengan data rekapan.",
        )
        main_layout.addWidget(header)

        # Banner Info
        self._banner = InfoBanner("", "info")
        self._banner.setVisible(False)
        main_layout.addWidget(self._banner)

        # Baris Pemilihan Contoh Dokumen PDF
        row_pdf = QHBoxLayout()
        row_pdf.setSpacing(10)

        lbl_pdf = QLabel("<b>Pilih Contoh Dokumen PDF:</b>")
        lbl_pdf.setStyleSheet(f"font-size: 13px; color: {COLORS.text_primary};")
        row_pdf.addWidget(lbl_pdf)

        self._combo_pdfs = QComboBox()
        self._combo_pdfs.setMinimumHeight(38)
        self._combo_pdfs.currentIndexChanged.connect(self._on_pdf_selected)
        row_pdf.addWidget(self._combo_pdfs, stretch=1)

        btn_tambah_pdf = SecondaryButton("+ Tambah Berkas PDF...")
        btn_tambah_pdf.setMinimumHeight(38)
        btn_tambah_pdf.clicked.connect(self._tambah_pdf)
        row_pdf.addWidget(btn_tambah_pdf)

        main_layout.addLayout(row_pdf)

        # Splitter Utama: Penampil PDF (Kiri) <-> Editor Field (Kanan)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── PANEL KIRI: PENAMPIL PDF ──────────────────────────────────────────
        panel_kiri = QFrame()
        layout_kiri = QVBoxLayout(panel_kiri)
        layout_kiri.setContentsMargins(0, 0, 0, 0)
        layout_kiri.setSpacing(8)

        lbl_kiri = QLabel("Pratinjau Dokumen PDF")
        lbl_kiri.setStyleSheet(f"font-weight: 600; color: {COLORS.text_primary};")
        layout_kiri.addWidget(lbl_kiri)

        self._pdf_viewer = PdfViewerWidget(self)
        layout_kiri.addWidget(self._pdf_viewer, stretch=1)

        splitter.addWidget(panel_kiri)

        # ── PANEL KANAN: DAFTAR FIELD & AKSI ──────────────────────────────────
        panel_kanan = QFrame()
        layout_kanan = QVBoxLayout(panel_kanan)
        layout_kanan.setContentsMargins(0, 0, 0, 0)
        layout_kanan.setSpacing(10)

        # Baris Judul & Tombol Tambah
        row_hdr_kanan = QHBoxLayout()
        lbl_kanan = QLabel("Daftar Field Dokumen")
        lbl_kanan.setStyleSheet(f"font-weight: 600; color: {COLORS.text_primary};")
        row_hdr_kanan.addWidget(lbl_kanan)
        row_hdr_kanan.addStretch()

        btn_tambah_field = PrimaryButton("+ Tambah Field")
        btn_tambah_field.clicked.connect(self._tambah_field)
        row_hdr_kanan.addWidget(btn_tambah_field)

        layout_kanan.addLayout(row_hdr_kanan)

        # Tabel Field
        self._table_model = FieldTableModel(self)
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table_view.clicked.connect(self._on_table_clicked)
        layout_kanan.addWidget(self._table_view, stretch=1)

        # Baris Tombol Aksi Tabel
        row_aksi = QHBoxLayout()
        row_aksi.setSpacing(8)

        btn_edit = SecondaryButton("Ubah Field")
        btn_edit.clicked.connect(self._edit_field)
        row_aksi.addWidget(btn_edit)

        btn_hapus = DangerButton("Hapus Field")
        btn_hapus.clicked.connect(self._hapus_field)
        row_aksi.addWidget(btn_hapus)

        row_aksi.addStretch()

        self._btn_uji = PrimaryButton("Uji Ekstraksi pada PDF Ini")
        self._btn_uji.clicked.connect(self._uji_ekstraksi)
        row_aksi.addWidget(self._btn_uji)

        layout_kanan.addLayout(row_aksi)

        splitter.addWidget(panel_kanan)
        splitter.setSizes([450, 550])

        main_layout.addWidget(splitter, stretch=1)

    def _tambah_pdf(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Pilih Contoh Berkas PDF",
            "",
            "Berkas PDF (*.pdf)",
        )
        if not paths:
            return

        for p in paths:
            if p not in self._pdf_paths:
                self._pdf_paths.append(p)
                self._combo_pdfs.addItem(Path(p).name, userData=p)

        if self._combo_pdfs.count() > 0:
            self._combo_pdfs.setCurrentIndex(self._combo_pdfs.count() - 1)

    def _on_pdf_selected(self, index: int) -> None:
        if index < 0 or index >= len(self._pdf_paths):
            return
        path = self._pdf_paths[index]
        self._pdf_viewer.load_pdf(path)

    def _tambah_field(self) -> None:
        dialog = FieldDialog(None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_field = dialog.get_definisi_field()
            self._fields.append(new_field)
            self._table_model.set_fields(self._fields, self._nilai_uji)
            self.fields_updated.emit(self._fields, self._pdf_paths)

    def _edit_field(self) -> None:
        row = self._table_view.currentIndex().row()
        field = self._table_model.get_field(row)
        if not field:
            QMessageBox.information(self, "Pemberitahuan", "Pilih field yang ingin diubah terlebih dahulu.")
            return

        dialog = FieldDialog(field, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_field = dialog.get_definisi_field()
            self._fields[row] = updated_field
            self._table_model.set_fields(self._fields, self._nilai_uji)
            self.fields_updated.emit(self._fields, self._pdf_paths)

    def _hapus_field(self) -> None:
        row = self._table_view.currentIndex().row()
        field = self._table_model.get_field(row)
        if not field:
            QMessageBox.information(self, "Pemberitahuan", "Pilih field yang ingin dihapus terlebih dahulu.")
            return

        konfirmasi = QMessageBox.question(
            self,
            "Konfirmasi Hapus",
            f"Apakah Anda yakin ingin menghapus field '{field.nama}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if konfirmasi == QMessageBox.StandardButton.Yes:
            self._fields.pop(row)
            self._nilai_uji.pop(field.nama, None)
            self._table_model.set_fields(self._fields, self._nilai_uji)
            self.fields_updated.emit(self._fields, self._pdf_paths)

    def _on_table_clicked(self, index: QModelIndex) -> None:
        row = index.row()
        field = self._table_model.get_field(row)
        if not field:
            return

        nf = self._nilai_uji.get(field.nama)
        if nf and nf.kotak:
            # Highlight kotak ekstraksi di penampil PDF
            x0, y0, x1, y1 = nf.kotak
            self._pdf_viewer.set_highlight_box(QRectF(x0, y0, x1 - x0, y1 - y0))
            if nf.halaman > 0:
                self._pdf_viewer.show_page(nf.halaman)
        elif field.cara_ambil == "area":
            kotak = field.parameter.get("kotak")
            if kotak and len(kotak) == 4:
                x0, y0, x1, y1 = kotak
                self._pdf_viewer.set_highlight_box(QRectF(x0, y0, x1 - x0, y1 - y0))
                self._pdf_viewer.show_page(field.parameter.get("halaman", 1))
        else:
            self._pdf_viewer.set_highlight_box(None)

    def _uji_ekstraksi(self) -> None:
        if not self._pdf_paths:
            self._tampilkan_banner("Silakan muat berkas PDF contoh terlebih dahulu.", "warning")
            return
        if not self._fields:
            self._tampilkan_banner("Silakan buat setidaknya satu Definisi Field.", "warning")
            return

        idx = self._combo_pdfs.currentIndex()
        if idx < 0:
            return
        pdf_path = self._pdf_paths[idx]

        try:
            doc_data = baca_pdf(Path(pdf_path))
            hasil_tuple = ekstrak_semua_field(
                definisi_list=self._fields,
                hasil_baca_pdf=doc_data,
            )
            self._nilai_uji = {nf.nama_field: nf for nf in hasil_tuple}
            self._table_model.set_nilai_uji(self._nilai_uji)

            berhasil = sum(1 for nf in hasil_tuple if nf.nilai_mentah.strip())
            self._tampilkan_banner(
                f"Uji ekstraksi selesai: {berhasil} dari {len(self._fields)} field berhasil diekstrak.",
                "success",
            )
        except Exception as e:
            self._tampilkan_banner(f"Gagal mengekstrak field: {e}", "error")

    def _tampilkan_banner(self, pesan: str, tipe: str) -> None:
        self._banner.set_state(pesan, tipe)
        self._banner.setVisible(True)

    def set_fields_and_pdfs(self, fields: list[DefinisiField], pdfs: list[str]) -> None:
        self._fields = list(fields)
        self._pdf_paths = list(pdfs)
        self._combo_pdfs.clear()
        for p in self._pdf_paths:
            self._combo_pdfs.addItem(Path(p).name, userData=p)
        self._table_model.set_fields(self._fields, self._nilai_uji)
        if self._pdf_paths:
            self._combo_pdfs.setCurrentIndex(0)

    def dapatkan_fields(self) -> list[DefinisiField]:
        return list(self._fields)

    def dapatkan_contoh_pdfs(self) -> list[str]:
        return list(self._pdf_paths)

    def is_valid_step(self) -> bool:
        """Langkah 2 valid jika sudah ada setidaknya 1 field yang didefinisikan."""
        return len(self._fields) > 0
