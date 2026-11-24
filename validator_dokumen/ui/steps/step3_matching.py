"""
ui/steps/step3_matching.py - Langkah 3: Pencocokan (Matching Builder) Dinamis.

Menyusun skema pencocokan K dari N, menghubungkan kolom rekapan dan field dokumen,
menentukan peran (Kunci/Pembanding), mode kecocokan, toleransi numerik/fuzzy, opsi
normalisasi komprehensif, saran pemetaan otomatis, serta analisis kualitas kunci.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from rapidfuzz import fuzz

from validator_dokumen.core.matcher import uji_tabrakan
from validator_dokumen.core.models import (
    DefinisiField,
    JikaAdaTidakCocok,
    ModeCocok,
    OpsiNormalisasi,
    PasanganPencocokan,
    PeranPasangan,
    SkemaPencocokan,
    TabelRekap,
)
from validator_dokumen.core.recap_table import IndeksRekap
from validator_dokumen.ui.theme import COLORS
from validator_dokumen.ui.widgets.buttons import DangerButton, PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.card import Card
from validator_dokumen.ui.widgets.info_banner import InfoBanner
from validator_dokumen.ui.widgets.labeled_field import LabeledField
from validator_dokumen.ui.widgets.section_header import SectionHeader


class PasanganTableModel(QAbstractTableModel):
    """Model tabel pasangan pencocokan dalam satu skema."""

    HEADERS: ClassVar[list[str]] = [
        "Kolom Rekapan",
        "Field Dokumen",
        "Peran",
        "Mode",
        "Ambang / Parameter",
        "Normalisasi",
        "Pesan Kustom",
    ]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pasangan: list[PasanganPencocokan] = []

    def set_pasangan(self, pasangan: list[PasanganPencocokan]) -> None:
        self.beginResetModel()
        self._pasangan = list(pasangan)
        self.endResetModel()

    def get_pasangan(self, index: int) -> PasanganPencocokan | None:
        if 0 <= index < len(self._pasangan):
            return self._pasangan[index]
        return None

    def get_all(self) -> list[PasanganPencocokan]:
        return list(self._pasangan)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._pasangan)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        elif orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._pasangan)):
            return None

        p = self._pasangan[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return p.kolom_rekap
            elif col == 1:
                return p.field_dokumen
            elif col == 2:
                return p.peran.value.upper()
            elif col == 3:
                return p.mode.value
            elif col == 4:
                if p.mode == ModeCocok.MIRIP:
                    return f"Ambang >= {p.ambang_mirip:.0f}%"
                elif p.mode == ModeCocok.NUMERIK:
                    return f"Tol <= {p.toleransi_numerik}"
                return "-"
            elif col == 5:
                # Ringkasan normalisasi aktif
                opts = []
                if p.normalisasi.abaikan_huruf_besar:
                    opts.append("Aa")
                if p.normalisasi.abaikan_spasi:
                    opts.append("Spasi")
                if p.normalisasi.abaikan_tanda_baca:
                    opts.append("Punct")
                if p.normalisasi.abaikan_awalan_badan_usaha:
                    opts.append("PT/CV")
                if p.normalisasi.abaikan_nol_depan:
                    opts.append("0...")
                if p.normalisasi.koreksi_ocr:
                    opts.append("OCR")
                return ", ".join(opts) if opts else "(Tanpa)"
            elif col == 6:
                return p.pesan_kesalahan_kustom or "-"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [2, 4]:
                return int(Qt.AlignmentFlag.AlignCenter)
        return None


class PasanganDialog(QDialog):
    """Dialog untuk menambah atau mengubah PasanganPencocokan."""

    def __init__(
        self,
        kolom_rekap: list[str],
        field_dokumen: list[str],
        pasangan: PasanganPencocokan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tambah Pasangan Pencocokan" if not pasangan else "Ubah Pasangan")
        self.resize(520, 500)
        self._kolom_rekap = kolom_rekap
        self._field_dokumen = field_dokumen
        self._existing_pasangan = pasangan

        self._setup_ui()
        if pasangan:
            self._load_from_pasangan(pasangan)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        # Dropdown Kolom Rekapan
        self._combo_rekap = QComboBox()
        for k in self._kolom_rekap:
            self._combo_rekap.addItem(k)
        form.addRow("<b>Kolom Rekapan:</b>", self._combo_rekap)

        # Dropdown Field Dokumen
        self._combo_field = QComboBox()
        for f in self._field_dokumen:
            self._combo_field.addItem(f)
        form.addRow("<b>Field Dokumen:</b>", self._combo_field)

        # Dropdown Peran
        self._combo_peran = QComboBox()
        self._combo_peran.addItem("KUNCI (Harus Cocok untuk Menemukan Baris)", PeranPasangan.KUNCI)
        self._combo_peran.addItem("PEMBANDING (Diperiksa Setelah Baris Ditemukan)", PeranPasangan.PEMBANDING)
        form.addRow("<b>Peran Pasangan:</b>", self._combo_peran)

        # Dropdown Mode
        self._combo_mode = QComboBox()
        for m in ModeCocok:
            self._combo_mode.addItem(m.value, m)
        self._combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("<b>Mode Pencocokan:</b>", self._combo_mode)

        # Parameter Khusus Mode
        # Mode: Mirip (Slider Ambang %)
        self._widget_mirip = QWidget()
        w_layout = QHBoxLayout(self._widget_mirip)
        w_layout.setContentsMargins(0, 0, 0, 0)
        self._slider_ambang = QSlider(Qt.Orientation.Horizontal)
        self._slider_ambang.setRange(50, 100)
        self._slider_ambang.setValue(90)
        self._lbl_ambang = QLabel("90%")
        self._slider_ambang.valueChanged.connect(lambda v: self._lbl_ambang.setText(f"{v}%"))
        w_layout.addWidget(self._slider_ambang)
        w_layout.addWidget(self._lbl_ambang)
        form.addRow("Ambang Kemiripan:", self._widget_mirip)

        # Mode: Numerik (Toleransi Selisih)
        self._widget_numerik = QWidget()
        n_layout = QHBoxLayout(self._widget_numerik)
        n_layout.setContentsMargins(0, 0, 0, 0)
        self._spin_toleransi = QDoubleSpinBox()
        self._spin_toleransi.setRange(0.0, 1000000.0)
        self._spin_toleransi.setValue(0.0)
        n_layout.addWidget(self._spin_toleransi)
        form.addRow("Toleransi Selisih:", self._widget_numerik)

        layout.addLayout(form)

        # Group Box: Opsi Normalisasi
        grp_norm = QGroupBox("Opsi Normalisasi (Centang yang Ingin Diabaikan)")
        norm_layout = QVBoxLayout(grp_norm)
        norm_layout.setSpacing(6)

        self._chk_huruf_besar = QCheckBox("Abaikan huruf besar/kecil (case-insensitive)")
        self._chk_huruf_besar.setChecked(True)
        norm_layout.addWidget(self._chk_huruf_besar)

        self._chk_spasi = QCheckBox("Abaikan spasi ekstra & spasi di depan/belakang")
        self._chk_spasi.setChecked(True)
        norm_layout.addWidget(self._chk_spasi)

        self._chk_tanda_baca = QCheckBox("Abaikan tanda baca (titik, koma, strip, garis miring)")
        norm_layout.addWidget(self._chk_tanda_baca)

        self._chk_badan_usaha = QCheckBox("Hapus awalan badan usaha (PT, CV, UD, PD, Tbk)")
        norm_layout.addWidget(self._chk_badan_usaha)

        self._chk_nol_depan = QCheckBox("Hapus nol di depan angka (contoh: 00123 -> 123)")
        norm_layout.addWidget(self._chk_nol_depan)

        self._chk_ocr = QCheckBox("Koreksi karakter OCR serupa (O/0, I/1, S/5, B/8, Z/2)")
        norm_layout.addWidget(self._chk_ocr)

        layout.addWidget(grp_norm)

        # Pesan Kesalahan Kustom
        layout.addWidget(QLabel("Pesan Kesalahan Kustom (Opsional):"))
        self._edit_pesan = QLineEdit()
        self._edit_pesan.setPlaceholderText("Biarkan kosong untuk pesan kesalahan default sistem")
        layout.addWidget(self._edit_pesan)

        # Tombol Aksi Dialog
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._on_mode_changed(0)

    def _on_mode_changed(self, index: int) -> None:
        mode = self._combo_mode.currentData()
        self._widget_mirip.setVisible(mode == ModeCocok.MIRIP)
        self._widget_numerik.setVisible(mode == ModeCocok.NUMERIK)

    def _load_from_pasangan(self, p: PasanganPencocokan) -> None:
        idx_r = self._combo_rekap.findText(p.kolom_rekap)
        if idx_r >= 0:
            self._combo_rekap.setCurrentIndex(idx_r)

        idx_f = self._combo_field.findText(p.field_dokumen)
        if idx_f >= 0:
            self._combo_field.setCurrentIndex(idx_f)

        idx_p = self._combo_peran.findData(p.peran)
        if idx_p >= 0:
            self._combo_peran.setCurrentIndex(idx_p)

        idx_m = self._combo_mode.findData(p.mode)
        if idx_m >= 0:
            self._combo_mode.setCurrentIndex(idx_m)

        self._slider_ambang.setValue(int(p.ambang_mirip))
        self._spin_toleransi.setValue(p.toleransi_numerik)

        self._chk_huruf_besar.setChecked(p.normalisasi.abaikan_huruf_besar)
        self._chk_spasi.setChecked(p.normalisasi.abaikan_spasi)
        self._chk_tanda_baca.setChecked(p.normalisasi.abaikan_tanda_baca)
        self._chk_badan_usaha.setChecked(p.normalisasi.abaikan_awalan_badan_usaha)
        self._chk_nol_depan.setChecked(p.normalisasi.abaikan_nol_depan)
        self._chk_ocr.setChecked(p.normalisasi.koreksi_ocr)

        self._edit_pesan.setText(p.pesan_kesalahan_kustom)

    def _validate_and_accept(self) -> None:
        if self._combo_rekap.currentIndex() < 0:
            QMessageBox.warning(self, "Peringatan", "Pilih kolom rekapan terlebih dahulu.")
            return
        if self._combo_field.currentIndex() < 0:
            QMessageBox.warning(self, "Peringatan", "Pilih field dokumen terlebih dahulu.")
            return
        self.accept()

    def get_pasangan(self) -> PasanganPencocokan:
        kolom_rekap = self._combo_rekap.currentText()
        field_dokumen = self._combo_field.currentText()
        peran = self._combo_peran.currentData()
        mode = self._combo_mode.currentData()

        opsi = OpsiNormalisasi(
            abaikan_huruf_besar=self._chk_huruf_besar.isChecked(),
            abaikan_spasi=self._chk_spasi.isChecked(),
            abaikan_tanda_baca=self._chk_tanda_baca.isChecked(),
            abaikan_awalan_badan_usaha=self._chk_badan_usaha.isChecked(),
            abaikan_nol_depan=self._chk_nol_depan.isChecked(),
            koreksi_ocr=self._chk_ocr.isChecked(),
            hapus_karakter_tak_terlihat=True,
        )

        p_id = self._existing_pasangan.id if self._existing_pasangan else str(uuid.uuid4())
        return PasanganPencocokan(
            id=p_id,
            kolom_rekap=kolom_rekap,
            field_dokumen=field_dokumen,
            peran=peran,
            mode=mode,
            normalisasi=opsi,
            ambang_mirip=float(self._slider_ambang.value()),
            toleransi_numerik=float(self._spin_toleransi.value()),
            pesan_kesalahan_kustom=self._edit_pesan.text().strip(),
        )


class Step3Matching(QWidget):
    """Layar Langkah 3: Pencocokan (Matching Builder) Dinamis."""

    # Sinyal saat skema diperbarui (list[SkemaPencocokan])
    schemas_updated = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tabel_rekap: TabelRekap | None = None
        self._fields: list[DefinisiField] = []
        self._skema_list: list[SkemaPencocokan] = []
        self._skema_aktif_idx: int = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header Langkah
        header = SectionHeader(
            title="Langkah 3: Pemetaan Pencocokan (Matching Builder)",
            subtitle="Petakan pasangan kolom rekapan dengan field dokumen izin. "
            "Tentukan peran KUNCI untuk pencarian baris, ambang skor K dari N, dan opsi normalisasi.",
        )
        main_layout.addWidget(header)

        # Banner Info
        self._banner = InfoBanner("", "info")
        self._banner.setVisible(False)
        main_layout.addWidget(self._banner)

        # Baris Pemilihan & Manajemen Skema
        row_skema = QHBoxLayout()
        row_skema.setSpacing(10)

        row_skema.addWidget(QLabel("<b>Pilih Skema Pencocokan:</b>"))
        self._combo_skema = QComboBox()
        self._combo_skema.currentIndexChanged.connect(self._on_skema_selected)
        row_skema.addWidget(self._combo_skema, stretch=2)

        btn_tambah_skema = SecondaryButton("+ Tambah Skema")
        btn_tambah_skema.clicked.connect(self._tambah_skema)
        row_skema.addWidget(btn_tambah_skema)

        btn_hapus_skema = DangerButton("Hapus Skema")
        btn_hapus_skema.clicked.connect(self._hapus_skema)
        row_skema.addWidget(btn_hapus_skema)

        row_skema.addStretch()

        btn_saran = PrimaryButton("🪄 Saran Pemetaan Otomatis")
        btn_saran.clicked.connect(self._sarankan_pemetaan)
        row_skema.addWidget(btn_saran)

        main_layout.addLayout(row_skema)

        # Card Parameter Skema Aktif (Nama, K dari N, Perlakuan)
        card_param = Card()
        layout_param = QHBoxLayout()
        layout_param.setSpacing(16)

        self._edit_nama_skema = QLineEdit("Skema Utama")
        self._edit_nama_skema.textChanged.connect(self._on_nama_skema_changed)
        f_nama = LabeledField("Nama Skema", self._edit_nama_skema)
        layout_param.addWidget(f_nama, stretch=2)

        self._spin_k = QSpinBox()
        self._spin_k.setRange(1, 100)
        self._spin_k.setValue(1)
        self._spin_k.valueChanged.connect(self._on_k_changed)
        self._lbl_total_n = QLabel("dari 0 pasangan")
        self._lbl_total_n.setStyleSheet(f"color: {COLORS.text_secondary}; font-size: 12px;")

        w_k = QWidget()
        box_k = QHBoxLayout(w_k)
        box_k.setContentsMargins(0, 0, 0, 0)
        box_k.addWidget(self._spin_k)
        box_k.addWidget(self._lbl_total_n)
        f_k = LabeledField("Ambang Cocok (K dari N)", w_k)
        layout_param.addWidget(f_k, stretch=2)

        self._combo_perlakuan = QComboBox()
        self._combo_perlakuan.addItem("Tandai VALID (dengan catatan)", JikaAdaTidakCocok.VALID_CATATAN)
        self._combo_perlakuan.addItem("Tandai PERLU DICEK", JikaAdaTidakCocok.PERLU_DICEK)
        self._combo_perlakuan.addItem("Tandai TIDAK VALID", JikaAdaTidakCocok.TIDAK_VALID)
        self._combo_perlakuan.currentIndexChanged.connect(self._on_perlakuan_changed)
        f_perlakuan = LabeledField("Jika K Cocok Tapi Ada Pasangan Beda", self._combo_perlakuan)
        layout_param.addWidget(f_perlakuan, stretch=3)

        card_param.layout().addLayout(layout_param)
        main_layout.addWidget(card_param)

        # Splitter: Tabel Pasangan (Atas) <-> Analisis Kualitas Kunci (Bawah)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Panel Tabel Pasangan
        panel_tabel = QFrame()
        layout_tabel = QVBoxLayout(panel_tabel)
        layout_tabel.setContentsMargins(0, 0, 0, 0)
        layout_tabel.setSpacing(8)

        row_hdr_tabel = QHBoxLayout()
        lbl_tabel_title = QLabel("Daftar Pasangan Kolom Rekapan <-> Field Dokumen")
        lbl_tabel_title.setStyleSheet(f"font-weight: 600; color: {COLORS.text_primary};")
        row_hdr_tabel.addWidget(lbl_tabel_title)
        row_hdr_tabel.addStretch()

        btn_tambah_p = PrimaryButton("+ Tambah Pasangan")
        btn_tambah_p.clicked.connect(self._tambah_pasangan)
        row_hdr_tabel.addWidget(btn_tambah_p)

        layout_tabel.addLayout(row_hdr_tabel)

        self._table_model = PasanganTableModel(self)
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        layout_tabel.addWidget(self._table_view, stretch=1)

        # Tombol Aksi Tabel Pasangan
        row_aksi_p = QHBoxLayout()
        row_aksi_p.setSpacing(8)

        btn_edit_p = SecondaryButton("Ubah Pasangan")
        btn_edit_p.clicked.connect(self._edit_pasangan)
        row_aksi_p.addWidget(btn_edit_p)

        btn_hapus_p = DangerButton("Hapus Pasangan")
        btn_hapus_p.clicked.connect(self._hapus_pasangan)
        row_aksi_p.addWidget(btn_hapus_p)

        row_aksi_p.addStretch()

        btn_naik = SecondaryButton("▲ Naikkan Urutan")
        btn_naik.clicked.connect(self._pindah_atas)
        row_aksi_p.addWidget(btn_naik)

        btn_turun = SecondaryButton("▼ Turunkan Urutan")
        btn_turun.clicked.connect(self._pindah_bawah)
        row_aksi_p.addWidget(btn_turun)

        layout_tabel.addLayout(row_aksi_p)
        splitter.addWidget(panel_tabel)

        # Panel Analisis Kualitas Kunci
        self._card_analisis = Card()
        layout_analisis = QVBoxLayout()
        layout_analisis.setSpacing(6)

        lbl_analisis_title = QLabel("Analisis Kualitas Kunci (Deteksi Tabrakan Baris Acuan)")
        lbl_analisis_title.setStyleSheet(f"font-weight: 600; color: {COLORS.text_primary};")
        layout_analisis.addWidget(lbl_analisis_title)

        self._lbl_analisis_kunci = QLabel("Belum ada pasangan dengan peran KUNCI.")
        self._lbl_analisis_kunci.setWordWrap(True)
        self._lbl_analisis_kunci.setStyleSheet(f"color: {COLORS.text_secondary}; font-size: 12px;")
        layout_analisis.addWidget(self._lbl_analisis_kunci)

        self._card_analisis.layout().addLayout(layout_analisis)
        splitter.addWidget(self._card_analisis)

        splitter.setSizes([340, 110])
        main_layout.addWidget(splitter, stretch=1)

    def set_context(
        self,
        tabel_rekap: TabelRekap | None,
        fields: list[DefinisiField],
        skema_list: list[SkemaPencocokan] | None = None,
    ) -> None:
        self._tabel_rekap = tabel_rekap
        self._fields = list(fields)

        if skema_list:
            self._skema_list = [
                SkemaPencocokan(
                    id=s.id,
                    nama=s.nama,
                    pasangan=tuple(s.pasangan),
                    k_minimum=s.k_minimum,
                    aktif=s.aktif,
                    gunakan_bobot=s.gunakan_bobot,
                    jika_ada_tidak_cocok=s.jika_ada_tidak_cocok,
                    min_selisih_skor=s.min_selisih_skor,
                )
                for s in skema_list
            ]
        elif not self._skema_list:
            # Buat skema default
            default_skema = SkemaPencocokan(
                id=str(uuid.uuid4()),
                nama="Skema Utama",
                pasangan=(),
                k_minimum=1,
            )
            self._skema_list = [default_skema]

        self._refresh_combo_skema()

    def _refresh_combo_skema(self) -> None:
        self._combo_skema.blockSignals(True)
        self._combo_skema.clear()
        for s in self._skema_list:
            self._combo_skema.addItem(s.nama)
        self._combo_skema.blockSignals(False)

        if 0 <= self._skema_aktif_idx < len(self._skema_list):
            self._combo_skema.setCurrentIndex(self._skema_aktif_idx)
            self._muat_skema_ke_form(self._skema_list[self._skema_aktif_idx])

    def _on_skema_selected(self, index: int) -> None:
        if 0 <= index < len(self._skema_list):
            self._skema_aktif_idx = index
            self._muat_skema_ke_form(self._skema_list[index])

    def _muat_skema_ke_form(self, s: SkemaPencocokan) -> None:
        self._edit_nama_skema.blockSignals(True)
        self._edit_nama_skema.setText(s.nama)
        self._edit_nama_skema.blockSignals(False)

        self._spin_k.blockSignals(True)
        self._spin_k.setMaximum(max(1, len(s.pasangan)))
        self._spin_k.setValue(min(s.k_minimum, max(1, len(s.pasangan))))
        self._spin_k.blockSignals(False)

        self._lbl_total_n.setText(f"dari {len(s.pasangan)} pasangan")

        idx_p = self._combo_perlakuan.findData(s.jika_ada_tidak_cocok)
        if idx_p >= 0:
            self._combo_perlakuan.blockSignals(True)
            self._combo_perlakuan.setCurrentIndex(idx_p)
            self._combo_perlakuan.blockSignals(False)

        self._table_model.set_pasangan(list(s.pasangan))
        self._analisis_kualitas_kunci()

    def _on_nama_skema_changed(self, text: str) -> None:
        if 0 <= self._skema_aktif_idx < len(self._skema_list):
            cur = self._skema_list[self._skema_aktif_idx]
            updated = SkemaPencocokan(
                id=cur.id,
                nama=text.strip() or "Skema",
                pasangan=cur.pasangan,
                k_minimum=cur.k_minimum,
                aktif=cur.aktif,
                gunakan_bobot=cur.gunakan_bobot,
                jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
                min_selisih_skor=cur.min_selisih_skor,
            )
            self._skema_list[self._skema_aktif_idx] = updated
            self._combo_skema.setItemText(self._skema_aktif_idx, updated.nama)
            self.schemas_updated.emit(self._skema_list)

    def _on_k_changed(self, val: int) -> None:
        if 0 <= self._skema_aktif_idx < len(self._skema_list):
            cur = self._skema_list[self._skema_aktif_idx]
            updated = SkemaPencocokan(
                id=cur.id,
                nama=cur.nama,
                pasangan=cur.pasangan,
                k_minimum=val,
                aktif=cur.aktif,
                gunakan_bobot=cur.gunakan_bobot,
                jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
                min_selisih_skor=cur.min_selisih_skor,
            )
            self._skema_list[self._skema_aktif_idx] = updated
            self.schemas_updated.emit(self._skema_list)

    def _on_perlakuan_changed(self, idx: int) -> None:
        if 0 <= self._skema_aktif_idx < len(self._skema_list):
            cur = self._skema_list[self._skema_aktif_idx]
            updated = SkemaPencocokan(
                id=cur.id,
                nama=cur.nama,
                pasangan=cur.pasangan,
                k_minimum=cur.k_minimum,
                aktif=cur.aktif,
                gunakan_bobot=cur.gunakan_bobot,
                jika_ada_tidak_cocok=self._combo_perlakuan.currentData(),
                min_selisih_skor=cur.min_selisih_skor,
            )
            self._skema_list[self._skema_aktif_idx] = updated
            self.schemas_updated.emit(self._skema_list)

    def _tambah_skema(self) -> None:
        new_skema = SkemaPencocokan(
            id=str(uuid.uuid4()),
            nama=f"Skema {len(self._skema_list) + 1}",
            pasangan=(),
            k_minimum=1,
        )
        self._skema_list.append(new_skema)
        self._skema_aktif_idx = len(self._skema_list) - 1
        self._refresh_combo_skema()
        self.schemas_updated.emit(self._skema_list)

    def _hapus_skema(self) -> None:
        if len(self._skema_list) <= 1:
            QMessageBox.warning(self, "Peringatan", "Minimal harus ada satu skema pencocokan.")
            return

        konfirmasi = QMessageBox.question(
            self,
            "Konfirmasi Hapus",
            f"Hapus skema '{self._skema_list[self._skema_aktif_idx].nama}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if konfirmasi == QMessageBox.StandardButton.Yes:
            self._skema_list.pop(self._skema_aktif_idx)
            self._skema_aktif_idx = max(0, self._skema_aktif_idx - 1)
            self._refresh_combo_skema()
            self.schemas_updated.emit(self._skema_list)

    def _tambah_pasangan(self) -> None:
        kolom_list = list(self._tabel_rekap.kolom) if self._tabel_rekap else []
        field_list = [f.nama for f in self._fields]

        if not kolom_list:
            QMessageBox.warning(self, "Peringatan", "Belum ada kolom rekapan. Silakan muat rekapan di Langkah 1.")
            return
        if not field_list:
            QMessageBox.warning(self, "Peringatan", "Belum ada field dokumen. Silakan definisikan field di Langkah 2.")
            return

        dlg = PasanganDialog(kolom_list, field_list, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_p = dlg.get_pasangan()
            cur = self._skema_list[self._skema_aktif_idx]
            new_pasangan = (*cur.pasangan, new_p)
            updated = SkemaPencocokan(
                id=cur.id,
                nama=cur.nama,
                pasangan=new_pasangan,
                k_minimum=min(cur.k_minimum, len(new_pasangan)),
                aktif=cur.aktif,
                gunakan_bobot=cur.gunakan_bobot,
                jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
                min_selisih_skor=cur.min_selisih_skor,
            )
            self._skema_list[self._skema_aktif_idx] = updated
            self._muat_skema_ke_form(updated)
            self.schemas_updated.emit(self._skema_list)

    def _edit_pasangan(self) -> None:
        row = self._table_view.currentIndex().row()
        p = self._table_model.get_pasangan(row)
        if not p:
            QMessageBox.information(self, "Pemberitahuan", "Pilih pasangan yang ingin diubah terlebih dahulu.")
            return

        kolom_list = list(self._tabel_rekap.kolom) if self._tabel_rekap else []
        field_list = [f.nama for f in self._fields]

        dlg = PasanganDialog(kolom_list, field_list, p, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated_p = dlg.get_pasangan()
            cur = self._skema_list[self._skema_aktif_idx]
            p_list = list(cur.pasangan)
            p_list[row] = updated_p
            updated = SkemaPencocokan(
                id=cur.id,
                nama=cur.nama,
                pasangan=tuple(p_list),
                k_minimum=cur.k_minimum,
                aktif=cur.aktif,
                gunakan_bobot=cur.gunakan_bobot,
                jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
                min_selisih_skor=cur.min_selisih_skor,
            )
            self._skema_list[self._skema_aktif_idx] = updated
            self._muat_skema_ke_form(updated)
            self.schemas_updated.emit(self._skema_list)

    def _hapus_pasangan(self) -> None:
        row = self._table_view.currentIndex().row()
        p = self._table_model.get_pasangan(row)
        if not p:
            QMessageBox.information(self, "Pemberitahuan", "Pilih pasangan yang ingin dihapus terlebih dahulu.")
            return

        cur = self._skema_list[self._skema_aktif_idx]
        p_list = list(cur.pasangan)
        p_list.pop(row)
        new_k = max(1, min(cur.k_minimum, len(p_list)))
        updated = SkemaPencocokan(
            id=cur.id,
            nama=cur.nama,
            pasangan=tuple(p_list),
            k_minimum=new_k,
            aktif=cur.aktif,
            gunakan_bobot=cur.gunakan_bobot,
            jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
            min_selisih_skor=cur.min_selisih_skor,
        )
        self._skema_list[self._skema_aktif_idx] = updated
        self._muat_skema_ke_form(updated)
        self.schemas_updated.emit(self._skema_list)

    def _pindah_atas(self) -> None:
        row = self._table_view.currentIndex().row()
        if row <= 0:
            return
        cur = self._skema_list[self._skema_aktif_idx]
        p_list = list(cur.pasangan)
        p_list[row - 1], p_list[row] = p_list[row], p_list[row - 1]
        updated = SkemaPencocokan(
            id=cur.id,
            nama=cur.nama,
            pasangan=tuple(p_list),
            k_minimum=cur.k_minimum,
            aktif=cur.aktif,
            gunakan_bobot=cur.gunakan_bobot,
            jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
            min_selisih_skor=cur.min_selisih_skor,
        )
        self._skema_list[self._skema_aktif_idx] = updated
        self._muat_skema_ke_form(updated)
        self._table_view.selectRow(row - 1)
        self.schemas_updated.emit(self._skema_list)

    def _pindah_bawah(self) -> None:
        row = self._table_view.currentIndex().row()
        cur = self._skema_list[self._skema_aktif_idx]
        if row < 0 or row >= len(cur.pasangan) - 1:
            return
        p_list = list(cur.pasangan)
        p_list[row + 1], p_list[row] = p_list[row], p_list[row + 1]
        updated = SkemaPencocokan(
            id=cur.id,
            nama=cur.nama,
            pasangan=tuple(p_list),
            k_minimum=cur.k_minimum,
            aktif=cur.aktif,
            gunakan_bobot=cur.gunakan_bobot,
            jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
            min_selisih_skor=cur.min_selisih_skor,
        )
        self._skema_list[self._skema_aktif_idx] = updated
        self._muat_skema_ke_form(updated)
        self._table_view.selectRow(row + 1)
        self.schemas_updated.emit(self._skema_list)

    def _sarankan_pemetaan(self) -> None:
        """Usulkan pasangan pemetaan berdasarkan kemiripan nama kolom dan field."""
        if not self._tabel_rekap or not self._fields:
            QMessageBox.warning(
                self,
                "Peringatan",
                "Pastikan tabel rekapan dan daftar field dokumen sudah dimuat.",
            )
            return

        kolom_list = list(self._tabel_rekap.kolom)
        field_list = [f.nama for f in self._fields]

        saran_list: list[tuple[str, str, float]] = []
        for col in kolom_list:
            for fld in field_list:
                skor = fuzz.token_set_ratio(col.lower(), fld.lower())
                if skor >= 60.0:
                    saran_list.append((col, fld, skor))

        # Urutkan berdasarkan skor tertinggi
        saran_list.sort(key=lambda x: x[2], reverse=True)

        if not saran_list:
            QMessageBox.information(
                self,
                "Saran Pemetaan",
                "Tidak ditemukan kemiripan nama kolom dan field di atas ambang 60%.",
            )
            return

        teks_saran = "\n".join(
            f"• [{col}] <-> [{fld}] (Kemiripan: {skor:.0f}%)"
            for col, fld, skor in saran_list[:8]
        )
        konfirmasi = QMessageBox.question(
            self,
            "Saran Pemetaan Otomatis Ditemukan",
            f"Ditemukan {len(saran_list)} pasangan yang mirip:\n\n{teks_saran}\n\n"
            "Terapkan pasangan ini ke skema aktif?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if konfirmasi == QMessageBox.StandardButton.Yes:
            cur = self._skema_list[self._skema_aktif_idx]
            pasangan_lama = list(cur.pasangan)
            ada_rekap = {p.kolom_rekap for p in pasangan_lama}
            ada_field = {p.field_dokumen for p in pasangan_lama}

            for col, fld, _ in saran_list:
                if col not in ada_rekap and fld not in ada_field:
                    # Tentukan peran KUNCI jika ada kata 'nomor', 'id', 'no', 'kode'
                    is_kunci = any(k in col.lower() or k in fld.lower() for k in ["nomor", "no", "id", "kode"])
                    p_baru = PasanganPencocokan(
                        id=str(uuid.uuid4()),
                        kolom_rekap=col,
                        field_dokumen=fld,
                        peran=PeranPasangan.KUNCI if is_kunci else PeranPasangan.PEMBANDING,
                        mode=ModeCocok.PERSIS_NORMALISASI,
                        normalisasi=OpsiNormalisasi(),
                    )
                    pasangan_lama.append(p_baru)
                    ada_rekap.add(col)
                    ada_field.add(fld)

            new_k = max(1, len(pasangan_lama) * 3 // 4)
            updated = SkemaPencocokan(
                id=cur.id,
                nama=cur.nama,
                pasangan=tuple(pasangan_lama),
                k_minimum=new_k,
                aktif=cur.aktif,
                gunakan_bobot=cur.gunakan_bobot,
                jika_ada_tidak_cocok=cur.jika_ada_tidak_cocok,
                min_selisih_skor=cur.min_selisih_skor,
            )
            self._skema_list[self._skema_aktif_idx] = updated
            self._muat_skema_ke_form(updated)
            self.schemas_updated.emit(self._skema_list)

    def _analisis_kualitas_kunci(self) -> None:
        """Hitung tabrakan kunci pada rekapan dan perbarui tampilan analisis."""
        if not self._tabel_rekap or self._skema_aktif_idx < 0 or self._skema_aktif_idx >= len(self._skema_list):
            return

        cur = self._skema_list[self._skema_aktif_idx]
        kunci_list = [p for p in cur.pasangan if p.peran == PeranPasangan.KUNCI]

        if not kunci_list:
            self._lbl_analisis_kunci.setText(
                "⚠ Belum ada pasangan dengan peran KUNCI. Tentukan setidaknya satu pasangan KUNCI "
                "agar sistem dapat mencari baris rekapan yang tepat."
            )
            self._lbl_analisis_kunci.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 500;")
            return

        try:
            kolom_kunci = [p.kolom_rekap for p in cur.pasangan]
            opsi_norm = {p.kolom_rekap: p.normalisasi for p in cur.pasangan}
            indeks = IndeksRekap(self._tabel_rekap, kolom_kunci, opsi_norm)
            hasil_tabrakan = uji_tabrakan(cur, indeks)

            total = hasil_tabrakan["total_baris"]
            kembar = hasil_tabrakan["baris_dengan_kembaran"]
            persen = hasil_tabrakan["persen_tabrakan"]
            saran = hasil_tabrakan["saran"]

            nama_kunci = ", ".join(f"[{p.kolom_rekap}]" for p in kunci_list)
            if kembar == 0:
                self._lbl_analisis_kunci.setText(
                    f"✔ <b>Kombinasi Kunci Unik 100%:</b> {nama_kunci} "
                    f"membedakan seluruh {total:,} baris tanpa ada tabrakan."
                )
                self._lbl_analisis_kunci.setStyleSheet("color: #16A34A; font-size: 12px;")
            else:
                self._lbl_analisis_kunci.setText(
                    f"⚠ <b>Peringatan Tabrakan Kunci ({kembar} baris / {persen:.1f}%):</b> {saran}"
                )
                self._lbl_analisis_kunci.setStyleSheet("color: #D97706; font-size: 12px;")
        except Exception as e:
            self._lbl_analisis_kunci.setText(f"Gagal menganalisis kunci: {e}")
            self._lbl_analisis_kunci.setStyleSheet(f"color: {COLORS.text_secondary}; font-size: 12px;")

    def dapatkan_skema_list(self) -> list[SkemaPencocokan]:
        return list(self._skema_list)

    def is_valid_step(self) -> bool:
        """Langkah 3 valid jika ada skema dengan minimal 1 pasangan KUNCI."""
        if not self._skema_list:
            return False
        cur = self._skema_list[self._skema_aktif_idx]
        return any(p.peran == PeranPasangan.KUNCI for p in cur.pasangan)
