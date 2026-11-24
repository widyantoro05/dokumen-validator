"""
ui/steps/step4_rules.py - Langkah 4: Aturan Tambahan & Visual JIKA-MAKA Builder.

Memungkinkan pengguna menyusun aturan validasi per field (regex format, salah satu opsi,
panjang, logika tanggal) serta aturan kondisional JIKA-MAKA dinamis lewat antarmuka
visual tanpa perlu menulis kode.
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
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from validator_dokumen.core.models import (
    AksiKondisional,
    AturanField,
    DefinisiField,
    KondisiJikaMaka,
    OperatorKondisi,
    TabelRekap,
)
from validator_dokumen.ui.widgets.buttons import DangerButton, PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.section_header import SectionHeader


class AturanFieldTableModel(QAbstractTableModel):
    """Model tabel aturan validasi per field."""

    HEADERS: ClassVar[list[str]] = [
        "Field Target",
        "Tipe Aturan",
        "Parameter",
        "Pesan Kustom",
    ]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._aturan: list[AturanField] = []

    def set_aturan(self, aturan: list[AturanField]) -> None:
        self.beginResetModel()
        self._aturan = list(aturan)
        self.endResetModel()

    def get_aturan(self, index: int) -> AturanField | None:
        if 0 <= index < len(self._aturan):
            return self._aturan[index]
        return None

    def get_all(self) -> list[AturanField]:
        return list(self._aturan)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._aturan)

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
        if not index.isValid() or not (0 <= index.row() < len(self._aturan)):
            return None

        a = self._aturan[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return a.field_nama
            elif col == 1:
                return a.tipe_aturan
            elif col == 2:
                # Ringkasan parameter
                return ", ".join(f"{k}={v}" for k, v in a.parameter.items())
            elif col == 3:
                return a.pesan_kustom or "-"
        return None


class KondisiTableModel(QAbstractTableModel):
    """Model tabel aturan kondisional JIKA-MAKA."""

    HEADERS: ClassVar[list[str]] = [
        "JIKA (Kondisi)",
        "MAKA (Aksi)",
        "Pesan Kesalahan",
    ]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._kondisi: list[KondisiJikaMaka] = []

    def set_kondisi(self, kondisi: list[KondisiJikaMaka]) -> None:
        self.beginResetModel()
        self._kondisi = list(kondisi)
        self.endResetModel()

    def get_kondisi(self, index: int) -> KondisiJikaMaka | None:
        if 0 <= index < len(self._kondisi):
            return self._kondisi[index]
        return None

    def get_all(self) -> list[KondisiJikaMaka]:
        return list(self._kondisi)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._kondisi)

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
        if not index.isValid() or not (0 <= index.row() < len(self._kondisi)):
            return None

        k = self._kondisi[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                parts = []
                for exp in k.kondisi:
                    sumber = exp.get("sumber", "field")
                    target = exp.get("target", "")
                    op = exp.get("operator", "")
                    val = exp.get("nilai", "")
                    parts.append(f"{sumber}[{target}] {op} '{val}'")
                return " DAN ".join(parts)
            elif col == 1:
                return f"{k.aksi.value}: {k.parameter_aksi}"
            elif col == 2:
                return k.pesan_kustom or "-"
        return None


class AturanFieldDialog(QDialog):
    """Dialog untuk membuat atau mengubah AturanField."""

    def __init__(
        self,
        fields: list[str],
        aturan: AturanField | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tambah Aturan Field" if not aturan else "Ubah Aturan Field")
        self.resize(460, 360)
        self._fields = fields
        self._existing_aturan = aturan

        self._setup_ui()
        if aturan:
            self._load_from_aturan(aturan)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        self._combo_field = QComboBox()
        for f in self._fields:
            self._combo_field.addItem(f)
        form.addRow("<b>Field Target:</b>", self._combo_field)

        self._combo_tipe = QComboBox()
        self._combo_tipe.addItem("Format Pola (Regex)", "format_pola")
        self._combo_tipe.addItem("Salah Satu dari Daftar", "salah_satu")
        self._combo_tipe.addItem("Batas Panjang Karakter", "panjang")
        self._combo_tipe.addItem("Logika Tanggal (Bukan Masa Depan)", "tanggal_logika")
        self._combo_tipe.currentIndexChanged.connect(self._on_tipe_changed)
        form.addRow("<b>Tipe Aturan:</b>", self._combo_tipe)

        # Panel Parameter Spesifik
        self._edit_param1 = QLineEdit()
        self._edit_param1.setPlaceholderText(r"Contoh: ^[0-9]{4}/[A-Z]+$")
        self._lbl_param1 = QLabel("Pola Regex:")
        form.addRow(self._lbl_param1, self._edit_param1)

        self._edit_pesan = QLineEdit()
        self._edit_pesan.setPlaceholderText("Pesan saat aturan dilanggar (opsional)")
        form.addRow("Pesan Kustom:", self._edit_pesan)

        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._on_tipe_changed(0)

    def _on_tipe_changed(self, index: int) -> None:
        tipe = self._combo_tipe.currentData()
        if tipe == "format_pola":
            self._lbl_param1.setText("Pola Regex:")
            self._edit_param1.setPlaceholderText(r"Contoh: ^[0-9]{4}/[A-Z]+$")
        elif tipe == "salah_satu":
            self._lbl_param1.setText("Daftar Nilai (pisah koma):")
            self._edit_param1.setPlaceholderText("Contoh: AKTIF, BERLAKU, DISELESAIKAN")
        elif tipe == "panjang":
            self._lbl_param1.setText("Panjang Min, Max (contoh: 5, 20):")
            self._edit_param1.setPlaceholderText("Contoh: 5, 20")
        elif tipe == "tanggal_logika":
            self._lbl_param1.setText("Batas Tanggal:")
            self._edit_param1.setPlaceholderText("Contoh: <= hari_ini")

    def _load_from_aturan(self, a: AturanField) -> None:
        idx_f = self._combo_field.findText(a.field_nama)
        if idx_f >= 0:
            self._combo_field.setCurrentIndex(idx_f)

        idx_t = self._combo_tipe.findData(a.tipe_aturan)
        if idx_t >= 0:
            self._combo_tipe.setCurrentIndex(idx_t)

        if a.tipe_aturan == "format_pola":
            self._edit_param1.setText(a.parameter.get("pola", ""))
        elif a.tipe_aturan == "salah_satu":
            self._edit_param1.setText(", ".join(a.parameter.get("daftar", [])))
        elif a.tipe_aturan == "panjang":
            min_l = a.parameter.get("min", "")
            max_l = a.parameter.get("max", "")
            self._edit_param1.setText(f"{min_l}, {max_l}")

        self._edit_pesan.setText(a.pesan_kustom)

    def _validate_and_accept(self) -> None:
        if self._combo_field.currentIndex() < 0:
            QMessageBox.warning(self, "Peringatan", "Pilih field target terlebih dahulu.")
            return
        if not self._edit_param1.text().strip():
            QMessageBox.warning(self, "Peringatan", "Parameter aturan tidak boleh kosong.")
            return
        self.accept()

    def get_aturan(self) -> AturanField:
        field_nama = self._combo_field.currentText()
        tipe = str(self._combo_tipe.currentData())
        param: dict[str, Any] = {}
        val_str = self._edit_param1.text().strip()

        if tipe == "format_pola":
            param["pola"] = val_str
        elif tipe == "salah_satu":
            param["daftar"] = [v.strip() for v in val_str.split(",") if v.strip()]
        elif tipe == "panjang":
            parts = val_str.split(",")
            param["min"] = int(parts[0].strip()) if len(parts) > 0 and parts[0].strip().isdigit() else 0
            param["max"] = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 100
        elif tipe == "tanggal_logika":
            param["operator"] = "<="
            param["acuan"] = "hari_ini"

        a_id = self._existing_aturan.id if self._existing_aturan else str(uuid.uuid4())
        return AturanField(
            id=a_id,
            field_nama=field_nama,
            tipe_aturan=tipe,
            parameter=param,
            pesan_kustom=self._edit_pesan.text().strip(),
        )


class KondisiJikaMakaDialog(QDialog):
    """Dialog visual JIKA-MAKA untuk membuat aturan kondisional."""

    def __init__(
        self,
        kolom_rekap: list[str],
        field_dokumen: list[str],
        kondisi: KondisiJikaMaka | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tambah Aturan JIKA-MAKA" if not kondisi else "Ubah Aturan JIKA-MAKA")
        self.resize(560, 480)
        self._kolom_rekap = kolom_rekap
        self._field_dokumen = field_dokumen
        self._existing_kondisi = kondisi

        self._setup_ui()
        if kondisi:
            self._load_from_kondisi(kondisi)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ── BAGIAN JIKA ───────────────────────────────────────────────────────
        grp_jika = QGroupBox("JIKA (Kondisi Prasyarat)")
        jika_layout = QFormLayout(grp_jika)
        jika_layout.setSpacing(10)

        self._combo_sumber = QComboBox()
        self._combo_sumber.addItem("Field Dokumen", "field")
        self._combo_sumber.addItem("Kolom Rekapan", "rekap")
        self._combo_sumber.currentIndexChanged.connect(self._on_sumber_changed)
        jika_layout.addRow("Sumber Nilai:", self._combo_sumber)

        self._combo_target = QComboBox()
        jika_layout.addRow("Nama Target:", self._combo_target)

        self._combo_operator = QComboBox()
        for op in OperatorKondisi:
            self._combo_operator.addItem(op.value, op)
        jika_layout.addRow("Operator:", self._combo_operator)

        self._edit_nilai = QLineEdit()
        self._edit_nilai.setPlaceholderText("Nilai acuan perbandingan (contoh: AMDAL, AKTIF)")
        jika_layout.addRow("Nilai Acuan:", self._edit_nilai)

        layout.addWidget(grp_jika)

        # ── BAGIAN MAKA ───────────────────────────────────────────────────────
        grp_maka = QGroupBox("MAKA (Aksi Validasi yang Harus Dilakukan)")
        maka_layout = QFormLayout(grp_maka)
        maka_layout.setSpacing(10)

        self._combo_aksi = QComboBox()
        self._combo_aksi.addItem("Wajib Ada Field Dokumen", AksiKondisional.WAJIB_ADA_FIELD)
        self._combo_aksi.addItem("Kolom Rekapan Harus Bernilai", AksiKondisional.KOLOM_REKAP_HARUS_BERNILAI)
        self._combo_aksi.addItem("Field Harus Cocok dengan Kolom", AksiKondisional.FIELD_HARUS_COCOK_KOLOM)
        self._combo_aksi.addItem("Tandai Dokumen TIDAK VALID", AksiKondisional.TANDAI_TIDAK_VALID)
        self._combo_aksi.currentIndexChanged.connect(self._on_aksi_changed)
        maka_layout.addRow("Tipe Aksi:", self._combo_aksi)

        self._combo_param_field = QComboBox()
        for f in self._field_dokumen:
            self._combo_param_field.addItem(f)
        self._lbl_param_field = QLabel("Pilih Field Dokumen:")
        maka_layout.addRow(self._lbl_param_field, self._combo_param_field)

        self._edit_param_nilai = QLineEdit()
        self._lbl_param_nilai = QLabel("Nilai yang Diharuskan:")
        maka_layout.addRow(self._lbl_param_nilai, self._edit_param_nilai)

        layout.addWidget(grp_maka)

        # Pesan Kesalahan Kustom
        layout.addWidget(QLabel("Pesan Kesalahan Jika Kondisi MAKA Gagal:"))
        self._edit_pesan = QLineEdit()
        self._edit_pesan.setPlaceholderText("Contoh: Izin kategori AMDAL wajib memiliki nomor persetujuan teknis.")
        layout.addWidget(self._edit_pesan)

        # Tombol Dialog
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._on_sumber_changed(0)
        self._on_aksi_changed(0)

    def _on_sumber_changed(self, index: int) -> None:
        sumber = self._combo_sumber.currentData()
        self._combo_target.clear()
        if sumber == "field":
            for f in self._field_dokumen:
                self._combo_target.addItem(f)
        else:
            for k in self._kolom_rekap:
                self._combo_target.addItem(k)

    def _on_aksi_changed(self, index: int) -> None:
        aksi = self._combo_aksi.currentData()
        is_field = aksi in [AksiKondisional.WAJIB_ADA_FIELD, AksiKondisional.FIELD_HARUS_COCOK_KOLOM]
        is_nilai = aksi == AksiKondisional.KOLOM_REKAP_HARUS_BERNILAI

        self._combo_param_field.setVisible(is_field)
        self._lbl_param_field.setVisible(is_field)
        self._edit_param_nilai.setVisible(is_nilai)
        self._lbl_param_nilai.setVisible(is_nilai)

    def _load_from_kondisi(self, k: KondisiJikaMaka) -> None:
        if k.kondisi:
            exp = k.kondisi[0]
            sumber = exp.get("sumber", "field")
            idx_s = self._combo_sumber.findData(sumber)
            if idx_s >= 0:
                self._combo_sumber.setCurrentIndex(idx_s)
                self._on_sumber_changed(idx_s)

            idx_t = self._combo_target.findText(exp.get("target", ""))
            if idx_t >= 0:
                self._combo_target.setCurrentIndex(idx_t)

            op = exp.get("operator", "")
            for i in range(self._combo_operator.count()):
                if self._combo_operator.itemData(i).value == op:
                    self._combo_operator.setCurrentIndex(i)
                    break

            self._edit_nilai.setText(exp.get("nilai", ""))

        idx_a = self._combo_aksi.findData(k.aksi)
        if idx_a >= 0:
            self._combo_aksi.setCurrentIndex(idx_a)
            self._on_aksi_changed(idx_a)

        if "field" in k.parameter_aksi:
            idx_pf = self._combo_param_field.findText(k.parameter_aksi["field"])
            if idx_pf >= 0:
                self._combo_param_field.setCurrentIndex(idx_pf)

        if "nilai" in k.parameter_aksi:
            self._edit_param_nilai.setText(k.parameter_aksi["nilai"])

        self._edit_pesan.setText(k.pesan_kustom)

    def _validate_and_accept(self) -> None:
        if self._combo_target.currentIndex() < 0:
            QMessageBox.warning(self, "Peringatan", "Pilih target kondisi JIKA terlebih dahulu.")
            return
        self.accept()

    def get_kondisi(self) -> KondisiJikaMaka:
        sumber = self._combo_sumber.currentData()
        target = self._combo_target.currentText()
        op = self._combo_operator.currentData().value
        nilai = self._edit_nilai.text().strip()

        ekspresi = {
            "sumber": sumber,
            "target": target,
            "operator": op,
            "nilai": nilai,
            "hubungan": "DAN",
        }

        aksi = self._combo_aksi.currentData()
        param_aksi: dict[str, Any] = {}
        if aksi in [AksiKondisional.WAJIB_ADA_FIELD, AksiKondisional.FIELD_HARUS_COCOK_KOLOM]:
            param_aksi["field"] = self._combo_param_field.currentText()
        elif aksi == AksiKondisional.KOLOM_REKAP_HARUS_BERNILAI:
            param_aksi["nilai"] = self._edit_param_nilai.text().strip()

        k_id = self._existing_kondisi.id if self._existing_kondisi else str(uuid.uuid4())
        return KondisiJikaMaka(
            id=k_id,
            kondisi=(ekspresi,),
            aksi=aksi,
            parameter_aksi=param_aksi,
            pesan_kustom=self._edit_pesan.text().strip(),
        )


class Step4Rules(QWidget):
    """Layar Langkah 4: Aturan Tambahan & Visual JIKA-MAKA Builder."""

    rules_updated = Signal(list, list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tabel_rekap: TabelRekap | None = None
        self._fields: list[DefinisiField] = []
        self._aturan_field: list[AturanField] = []
        self._kondisi_list: list[KondisiJikaMaka] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        header = SectionHeader(
            title="Langkah 4: Aturan Tambahan & Aturan Kondisional (JIKA-MAKA)",
            subtitle="Tambahkan aturan validasi format pada field atau logika kondisional antar kolom/field.",
        )
        main_layout.addWidget(header)

        # Tab Widget: Tab 1 Aturan Field, Tab 2 Aturan JIKA-MAKA
        tabs = QTabWidget()

        # ── TAB 1: ATURAN FIELD ───────────────────────────────────────────────
        tab_field = QWidget()
        layout_tf = QVBoxLayout(tab_field)
        layout_tf.setContentsMargins(16, 16, 16, 16)
        layout_tf.setSpacing(10)

        row_hdr_af = QHBoxLayout()
        row_hdr_af.addWidget(QLabel("<b>Aturan Validasi Format per Field</b>"))
        row_hdr_af.addStretch()

        btn_tambah_af = PrimaryButton("+ Tambah Aturan Field")
        btn_tambah_af.clicked.connect(self._tambah_aturan_field)
        row_hdr_af.addWidget(btn_tambah_af)
        layout_tf.addLayout(row_hdr_af)

        self._model_af = AturanFieldTableModel(self)
        self._view_af = QTableView()
        self._view_af.setModel(self._model_af)
        self._view_af.horizontalHeader().setStretchLastSection(True)
        self._view_af.setAlternatingRowColors(True)
        self._view_af.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view_af.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        layout_tf.addWidget(self._view_af, stretch=1)

        row_btn_af = QHBoxLayout()
        btn_edit_af = SecondaryButton("Ubah Aturan")
        btn_edit_af.clicked.connect(self._edit_aturan_field)
        row_btn_af.addWidget(btn_edit_af)

        btn_hapus_af = DangerButton("Hapus Aturan")
        btn_hapus_af.clicked.connect(self._hapus_aturan_field)
        row_btn_af.addWidget(btn_hapus_af)
        row_btn_af.addStretch()
        layout_tf.addLayout(row_btn_af)

        tabs.addTab(tab_field, "Aturan Validasi Field")

        # ── TAB 2: ATURAN JIKA-MAKA ───────────────────────────────────────────
        tab_jika = QWidget()
        layout_tj = QVBoxLayout(tab_jika)
        layout_tj.setContentsMargins(16, 16, 16, 16)
        layout_tj.setSpacing(10)

        row_hdr_jm = QHBoxLayout()
        row_hdr_jm.addWidget(QLabel("<b>Aturan Logika Kondisional (Visual JIKA-MAKA Builder)</b>"))
        row_hdr_jm.addStretch()

        btn_tambah_jm = PrimaryButton("+ Tambah Aturan JIKA-MAKA")
        btn_tambah_jm.clicked.connect(self._tambah_kondisi)
        row_hdr_jm.addWidget(btn_tambah_jm)
        layout_tj.addLayout(row_hdr_jm)

        self._model_jm = KondisiTableModel(self)
        self._view_jm = QTableView()
        self._view_jm.setModel(self._model_jm)
        self._view_jm.horizontalHeader().setStretchLastSection(True)
        self._view_jm.setAlternatingRowColors(True)
        self._view_jm.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view_jm.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        layout_tj.addWidget(self._view_jm, stretch=1)

        row_btn_jm = QHBoxLayout()
        btn_edit_jm = SecondaryButton("Ubah Aturan")
        btn_edit_jm.clicked.connect(self._edit_kondisi)
        row_btn_jm.addWidget(btn_edit_jm)

        btn_hapus_jm = DangerButton("Hapus Aturan")
        btn_hapus_jm.clicked.connect(self._hapus_kondisi)
        row_btn_jm.addWidget(btn_hapus_jm)
        row_btn_jm.addStretch()
        layout_tj.addLayout(row_btn_jm)

        tabs.addTab(tab_jika, "Aturan Kondisional (JIKA-MAKA)")

        main_layout.addWidget(tabs, stretch=1)

    def set_context(
        self,
        tabel_rekap: TabelRekap | None,
        fields: list[DefinisiField],
        aturan_field: list[AturanField] | None = None,
        kondisi_list: list[KondisiJikaMaka] | None = None,
    ) -> None:
        self._tabel_rekap = tabel_rekap
        self._fields = list(fields)
        if aturan_field is not None:
            self._aturan_field = list(aturan_field)
            self._model_af.set_aturan(self._aturan_field)
        if kondisi_list is not None:
            self._kondisi_list = list(kondisi_list)
            self._model_jm.set_kondisi(self._kondisi_list)

    def _tambah_aturan_field(self) -> None:
        field_names = [f.nama for f in self._fields]
        if not field_names:
            QMessageBox.warning(self, "Peringatan", "Belum ada field dokumen yang didefinisikan.")
            return

        dlg = AturanFieldDialog(field_names, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_a = dlg.get_aturan()
            self._aturan_field.append(new_a)
            self._model_af.set_aturan(self._aturan_field)
            self.rules_updated.emit(self._aturan_field, self._kondisi_list)

    def _edit_aturan_field(self) -> None:
        row = self._view_af.currentIndex().row()
        a = self._model_af.get_aturan(row)
        if not a:
            QMessageBox.information(self, "Pemberitahuan", "Pilih aturan yang ingin diubah terlebih dahulu.")
            return

        field_names = [f.nama for f in self._fields]
        dlg = AturanFieldDialog(field_names, a, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._aturan_field[row] = dlg.get_aturan()
            self._model_af.set_aturan(self._aturan_field)
            self.rules_updated.emit(self._aturan_field, self._kondisi_list)

    def _hapus_aturan_field(self) -> None:
        row = self._view_af.currentIndex().row()
        if not self._model_af.get_aturan(row):
            QMessageBox.information(self, "Pemberitahuan", "Pilih aturan yang ingin dihapus terlebih dahulu.")
            return
        self._aturan_field.pop(row)
        self._model_af.set_aturan(self._aturan_field)
        self.rules_updated.emit(self._aturan_field, self._kondisi_list)

    def _tambah_kondisi(self) -> None:
        kolom_list = list(self._tabel_rekap.kolom) if self._tabel_rekap else []
        field_list = [f.nama for f in self._fields]

        dlg = KondisiJikaMakaDialog(kolom_list, field_list, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_k = dlg.get_kondisi()
            self._kondisi_list.append(new_k)
            self._model_jm.set_kondisi(self._kondisi_list)
            self.rules_updated.emit(self._aturan_field, self._kondisi_list)

    def _edit_kondisi(self) -> None:
        row = self._view_jm.currentIndex().row()
        k = self._model_jm.get_kondisi(row)
        if not k:
            QMessageBox.information(self, "Pemberitahuan", "Pilih aturan JIKA-MAKA yang ingin diubah.")
            return

        kolom_list = list(self._tabel_rekap.kolom) if self._tabel_rekap else []
        field_list = [f.nama for f in self._fields]

        dlg = KondisiJikaMakaDialog(kolom_list, field_list, k, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._kondisi_list[row] = dlg.get_kondisi()
            self._model_jm.set_kondisi(self._kondisi_list)
            self.rules_updated.emit(self._aturan_field, self._kondisi_list)

    def _hapus_kondisi(self) -> None:
        row = self._view_jm.currentIndex().row()
        if not self._model_jm.get_kondisi(row):
            QMessageBox.information(self, "Pemberitahuan", "Pilih aturan JIKA-MAKA yang ingin dihapus.")
            return
        self._kondisi_list.pop(row)
        self._model_jm.set_kondisi(self._kondisi_list)
        self.rules_updated.emit(self._aturan_field, self._kondisi_list)

    def dapatkan_aturan_field(self) -> list[AturanField]:
        return list(self._aturan_field)

    def dapatkan_kondisi_list(self) -> list[KondisiJikaMaka]:
        return list(self._kondisi_list)

    def is_valid_step(self) -> bool:
        """Langkah 4 bersifat opsional (selalu valid)."""
        return True
