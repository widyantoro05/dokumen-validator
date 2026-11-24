"""
ui/steps/step5_test_save.py - Langkah 5: Uji Pencocokan & Simpan Profil JSON.

Menjalankan uji pencocokan menyeluruh pada dokumen contoh untuk memverifikasi
ekstraksi, skema pencocokan, dan aturan sebelum profil disimpan sebagai JSON
atau diekspor ke disk.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.constants import PROFILE_SCHEMA_VERSION
from validator_dokumen.core.models import (
    AturanField,
    DefinisiField,
    HasilValidasiDokumen,
    KondisiJikaMaka,
    ProfilValidasi,
    SkemaPencocokan,
    StatusValidasi,
    TabelRekap,
)
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.ui.diff_label import DiffLabel
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.card import Card
from validator_dokumen.ui.widgets.info_banner import InfoBanner
from validator_dokumen.ui.widgets.section_header import SectionHeader


class TestResultsTableModel(QAbstractTableModel):
    """Model tabel untuk hasil pengujian contoh dokumen."""

    HEADERS: ClassVar[list[str]] = [
        "Nama Dokumen",
        "Status",
        "Skema Terpakai",
        "Skor (K/N)",
        "Baris Rekapan",
        "Catatan / Masalah",
    ]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hasil: list[HasilValidasiDokumen] = []

    def set_results(self, hasil: list[HasilValidasiDokumen]) -> None:
        self.beginResetModel()
        self._hasil = list(hasil)
        self.endResetModel()

    def get_item(self, index: int) -> HasilValidasiDokumen | None:
        if 0 <= index < len(self._hasil):
            return self._hasil[index]
        return None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._hasil)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._hasil)):
            return None

        h = self._hasil[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return h.nama_file
            elif col == 1:
                return h.status.value
            elif col == 2:
                return h.skema_terpakai or "-"
            elif col == 3:
                return f"{h.skor}/{h.skor_total}"
            elif col == 4:
                return str(h.nomor_baris_rekap) if h.nomor_baris_rekap else "-"
            elif col == 5:
                return "; ".join(h.masalah) if h.masalah else "-"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [1, 3, 4]:
                return int(Qt.AlignmentFlag.AlignCenter)
        return None


class Step5TestSave(QWidget):
    """Layar Langkah 5: Uji Pencocokan & Simpan Profil JSON."""

    # Sinyal saat profil berhasil disimpan (ProfilValidasi, path_file)
    profile_saved = Signal(object, str)
    # Sinyal untuk membuka layar validasi
    open_validation_view = Signal()

    def __init__(
        self,
        profile_service: ProfileService,
        validation_service: ValidationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ps = profile_service
        self._vs = validation_service

        self._tabel_rekap: TabelRekap | None = None
        self._contoh_pdfs: list[str] = []
        self._fields: list[DefinisiField] = []
        self._skema_list: list[SkemaPencocokan] = []
        self._aturan_field: list[AturanField] = []
        self._kondisi_list: list[KondisiJikaMaka] = []

        self._hasil_uji: list[HasilValidasiDokumen] = []
        self._profil_id: str = ""

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        header = SectionHeader(
            title="Langkah 5: Uji Pencocokan & Simpan Profil",
            subtitle="Jalankan pengujian langsung pada contoh dokumen izin, periksa hasilnya, "
            "dan simpan konfigurasi lengkap sebagai Profil Validasi JSON.",
        )
        main_layout.addWidget(header)

        # Banner Info
        self._banner = InfoBanner("", "info")
        self._banner.setVisible(False)
        main_layout.addWidget(self._banner)

        # Card Metadata Profil
        card_meta = Card()
        form_meta = QFormLayout()
        form_meta.setSpacing(10)

        self._edit_nama_profil = QLineEdit("Profil Validasi Baru")
        self._edit_nama_profil.setMinimumHeight(38)
        self._edit_nama_profil.textChanged.connect(self._on_nama_changed)
        form_meta.addRow("<b>Nama Profil:</b>", self._edit_nama_profil)

        self._edit_deskripsi = QTextEdit()
        self._edit_deskripsi.setPlaceholderText("Deskripsi tujuan profil atau jenis perizinan...")
        self._edit_deskripsi.setMaximumHeight(60)
        form_meta.addRow("Deskripsi:", self._edit_deskripsi)

        self._edit_id = QLineEdit()
        self._edit_id.setMinimumHeight(38)
        self._edit_id.setReadOnly(True)
        form_meta.addRow("ID Profil:", self._edit_id)

        card_meta.layout().addLayout(form_meta)
        main_layout.addWidget(card_meta)

        # Splitter: Tabel Hasil Uji (Kiri) <-> Rincian Perbandingan (Kanan)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel Kiri: Tabel Hasil
        panel_kiri = QFrame()
        layout_kiri = QVBoxLayout(panel_kiri)
        layout_kiri.setContentsMargins(0, 0, 0, 0)
        layout_kiri.setSpacing(8)

        row_hdr_uji = QHBoxLayout()
        row_hdr_uji.addWidget(QLabel("<b>Hasil Pengujian Contoh Dokumen</b>"))
        row_hdr_uji.addStretch()

        self._btn_uji = PrimaryButton("Uji Pencocokan pada Contoh Dokumen")
        self._btn_uji.clicked.connect(self._jalankan_uji)
        row_hdr_uji.addWidget(self._btn_uji)
        layout_kiri.addLayout(row_hdr_uji)

        self._table_model = TestResultsTableModel(self)
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table_view.clicked.connect(self._on_item_selected)
        layout_kiri.addWidget(self._table_view, stretch=1)

        splitter.addWidget(panel_kiri)

        # Panel Kanan: Rincian Pasangan Hasil Uji
        panel_kanan = QFrame()
        self._layout_kanan = QVBoxLayout(panel_kanan)
        self._layout_kanan.setContentsMargins(0, 0, 0, 0)
        self._layout_kanan.setSpacing(8)

        self._lbl_rincian_title = QLabel("Rincian Pasangan Pencocokan")
        self._lbl_rincian_title.setStyleSheet(f"font-weight: 600; color: {COLORS.text_primary};")
        self._layout_kanan.addWidget(self._lbl_rincian_title)

        self._diff_widget = DiffLabel()
        self._layout_kanan.addWidget(self._diff_widget)

        self._lbl_rincian_teks = QTextEdit()
        self._lbl_rincian_teks.setReadOnly(True)
        self._lbl_rincian_teks.setPlaceholderText("Pilih baris hasil uji di sebelah kiri untuk melihat rincian pasangan.")
        self._layout_kanan.addWidget(self._lbl_rincian_teks, stretch=1)

        splitter.addWidget(panel_kanan)
        splitter.setSizes([550, 450])
        main_layout.addWidget(splitter, stretch=1)

        # Baris Tombol Aksi Simpan & Ekspor
        row_bawah = QHBoxLayout()
        row_bawah.setSpacing(12)

        btn_ekspor = SecondaryButton("Ekspor Profil JSON...")
        btn_ekspor.clicked.connect(self._ekspor_profil)
        row_bawah.addWidget(btn_ekspor)

        row_bawah.addStretch()

        btn_simpan = PrimaryButton("Simpan Profil")
        btn_simpan.setMinimumWidth(140)
        btn_simpan.clicked.connect(self._simpan_profil)
        row_bawah.addWidget(btn_simpan)

        btn_selesai = SecondaryButton("Buka Layar Validasi ->")
        btn_selesai.clicked.connect(lambda: self.open_validation_view.emit())
        row_bawah.addWidget(btn_selesai)

        main_layout.addLayout(row_bawah)

    def set_context(
        self,
        tabel_rekap: TabelRekap | None,
        contoh_pdfs: list[str],
        fields: list[DefinisiField],
        skema_list: list[SkemaPencocokan],
        aturan_field: list[AturanField],
        kondisi_list: list[KondisiJikaMaka],
        profil_id: str = "",
        profil_nama: str = "",
        profil_deskripsi: str = "",
    ) -> None:
        self._tabel_rekap = tabel_rekap
        self._contoh_pdfs = list(contoh_pdfs)
        self._fields = list(fields)
        self._skema_list = list(skema_list)
        self._aturan_field = list(aturan_field)
        self._kondisi_list = list(kondisi_list)

        self._profil_id = profil_id or str(uuid.uuid4())
        self._edit_id.setText(self._profil_id)
        if profil_nama:
            self._edit_nama_profil.blockSignals(True)
            self._edit_nama_profil.setText(profil_nama)
            self._edit_nama_profil.blockSignals(False)
        if profil_deskripsi:
            self._edit_deskripsi.setText(profil_deskripsi)

    def _on_nama_changed(self, text: str) -> None:
        # Jika belum ada ID kustom, generate slug dari nama
        if not self._profil_id or self._profil_id.startswith("prof_"):
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
            self._profil_id = f"prof_{slug}" if slug else f"prof_{uuid.uuid4().hex[:8]}"
            self._edit_id.setText(self._profil_id)

    def _bangun_profil_objek(self) -> ProfilValidasi:
        return ProfilValidasi(
            schema_version=PROFILE_SCHEMA_VERSION,
            id=self._profil_id or str(uuid.uuid4()),
            nama=self._edit_nama_profil.text().strip() or "Profil Validasi",
            deskripsi=self._edit_deskripsi.toPlainText().strip(),
            field_dokumen=tuple(self._fields),
            skema_pencocokan=tuple(self._skema_list),
            aturan_field=tuple(self._aturan_field),
            kondisi_jika_maka=tuple(self._kondisi_list),
        )

    def _jalankan_uji(self) -> None:
        if not self._tabel_rekap:
            self._tampilkan_banner("Tabel rekapan belum dimuat di Langkah 1.", "warning")
            return
        if not self._contoh_pdfs:
            self._tampilkan_banner("Belum ada contoh PDF yang dimuat di Langkah 2.", "warning")
            return
        if not self._skema_list:
            self._tampilkan_banner("Belum ada skema pencocokan di Langkah 3.", "warning")
            return

        profil = self._bangun_profil_objek()
        hasil_list: list[HasilValidasiDokumen] = []

        try:
            for p in self._contoh_pdfs:
                h = self._vs.validasi_satu_file(
                    path_dokumen=p,
                    profil=profil,
                    tabel_rekap=self._tabel_rekap,
                )
                hasil_list.append(h)

            self._hasil_uji = hasil_list
            self._table_model.set_results(hasil_list)

            valid_count = sum(1 for h in hasil_list if h.status == StatusValidasi.VALID)
            self._tampilkan_banner(
                f"Pengujian selesai: {len(hasil_list)} dokumen diuji. {valid_count} VALID.",
                "success" if valid_count == len(hasil_list) else "info",
            )
        except Exception as e:
            self._tampilkan_banner(f"Gagal menjalankan uji pencocokan: {e}", "error")

    def _on_item_selected(self, index: QModelIndex) -> None:
        row = index.row()
        h = self._table_model.get_item(row)
        if not h:
            return

        teks_rincian = [
            f"Dokumen: {h.nama_file}",
            f"Status: {h.status.value}",
            f"Skema Terpakai: {h.skema_terpakai or '-'}",
            f"Skor Cocok: {h.skor}/{h.skor_total}",
            f"Baris Rekapan: {h.nomor_baris_rekap or '-'}",
            "",
            "Hasil Pasangan:",
        ]

        # Tampilkan rincian per pasangan
        for hp in h.hasil_pasangan:
            simbol = "✔" if hp.cocok else "✖"
            teks_rincian.append(
                f" {simbol} [{hp.kolom_rekap}] <-> [{hp.field_dokumen}] "
                f"| Dokumen: '{hp.nilai_dokumen}' | Rekap: '{hp.nilai_rekap}' ({hp.alasan})"
            )

        if h.masalah:
            teks_rincian.append("")
            teks_rincian.append("Masalah / Catatan:")
            for m in h.masalah:
                teks_rincian.append(f" • {m}")

        self._lbl_rincian_teks.setText("\n".join(teks_rincian))

        # Tampilkan perbandingan karakter pada pasangan pertama yang tidak cocok jika ada
        pasangan_beda = [hp for hp in h.hasil_pasangan if not hp.cocok]
        if pasangan_beda:
            first_beda = pasangan_beda[0]
            self._diff_widget.set_values(first_beda.nilai_dokumen, first_beda.nilai_rekap)
            self._diff_widget.setVisible(True)
        elif h.hasil_pasangan:
            first = h.hasil_pasangan[0]
            self._diff_widget.set_values(first.nilai_dokumen, first.nilai_rekap)
            self._diff_widget.setVisible(True)
        else:
            self._diff_widget.setVisible(False)

    def _simpan_profil(self) -> None:
        profil = self._bangun_profil_objek()
        try:
            path_file = self._ps.simpan_profil(profil)
            self._tampilkan_banner(f"Profil '{profil.nama}' berhasil disimpan ke: {path_file}", "success")
            self.profile_saved.emit(profil, str(path_file))
        except Exception as e:
            self._tampilkan_banner(f"Gagal menyimpan profil: {e}", "error")

    def _ekspor_profil(self) -> None:
        profil = self._bangun_profil_objek()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Ekspor Profil JSON",
            f"{profil.id}.json",
            "Berkas JSON (*.json)",
        )
        if not path:
            return

        try:
            self._ps.ekspor_profil(profil.id, Path(path))
            self._tampilkan_banner(f"Profil berhasil diekspor ke: {path}", "success")
        except Exception as e:
            self._tampilkan_banner(f"Gagal mengekspor profil: {e}", "error")

    def _tampilkan_banner(self, pesan: str, tipe: str) -> None:
        self._banner.set_state(pesan, tipe)
        self._banner.setVisible(True)

    def is_valid_step(self) -> bool:
        return bool(self._edit_nama_profil.text().strip())
