"""
tests/test_ui.py - Tes unit untuk antarmuka pengguna PySide6 (Headless Offscreen).
"""

from __future__ import annotations

import os
import sys

import pytest

# Pastikan platform offscreen untuk testing tanpa display fisik
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from validator_dokumen.core.models import (
    HasilBulk,
    HasilValidasiDokumen,
    StatusValidasi,
)
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.ui.diff_label import DiffLabel, _render_char_diff_html
from validator_dokumen.ui.main_window import MainWindow
from validator_dokumen.ui.results_view import FileFilterProxyModel, FileTableModel, ResultsView
from validator_dokumen.ui.theme import (
    COLORS,
    generate_qss,
    status_color_pair,
    status_icon_and_label,
)
from validator_dokumen.ui.validation_view import ValidationView
from validator_dokumen.ui.widgets.badges import StatusBadge
from validator_dokumen.ui.widgets.buttons import DangerButton, PrimaryButton, SecondaryButton
from validator_dokumen.ui.widgets.card import Card
from validator_dokumen.ui.widgets.info_banner import InfoBanner
from validator_dokumen.ui.widgets.labeled_field import LabeledField
from validator_dokumen.ui.widgets.stat_card import StatCard


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app  # type: ignore[return-value]


class TestTheme:
    def test_status_color_pairs(self) -> None:
        for status in StatusValidasi:
            txt, bg, border = status_color_pair(status)
            assert txt.startswith("#")
            assert bg.startswith("#")
            assert border.startswith("#")

    def test_status_icons_and_labels(self) -> None:
        for status in StatusValidasi:
            icon, label = status_icon_and_label(status)
            assert len(icon) > 0
            assert len(label) > 0

    def test_generate_qss(self) -> None:
        qss = generate_qss()
        assert "Segoe UI" in qss
        assert COLORS.accent in qss


class TestWidgets:
    def test_buttons(self, qapp: QApplication) -> None:
        b1 = PrimaryButton("Simpan")
        b2 = SecondaryButton("Batal")
        b3 = DangerButton("Hapus")
        assert b1.text() == "Simpan"
        assert b2.text() == "Batal"
        assert b3.text() == "Hapus"

    def test_status_badge(self, qapp: QApplication) -> None:
        badge = StatusBadge(StatusValidasi.VALID)
        assert "VALID" in badge.text()
        badge.set_status(StatusValidasi.TIDAK_VALID)
        assert "TIDAK VALID" in badge.text()

    def test_stat_card(self, qapp: QApplication) -> None:
        sc = StatCard(StatusValidasi.PERLU_DICEK, 15)
        assert sc._count == 15
        sc.set_count(20)
        assert sc._count == 20

    def test_card_and_banner(self, qapp: QApplication) -> None:
        card = Card()
        assert card.layout() is not None

        banner = InfoBanner("Peringatan", "warning")
        assert banner._lbl_message.text() == "Peringatan"

    def test_labeled_field(self, qapp: QApplication) -> None:
        from PySide6.QtWidgets import QLineEdit
        edit = QLineEdit()
        lf = LabeledField("Nama Dokumen", edit)
        assert lf.widget() is edit
        lf.set_error("Tidak boleh kosong")
        assert not lf._lbl_error.isHidden()
        lf.set_error("")
        assert lf._lbl_error.isHidden()


class TestDiffLabel:
    def test_diff_render_identical(self, qapp: QApplication) -> None:
        diff = DiffLabel()
        diff.set_values("123-ABC", "123-ABC")
        assert "123-ABC" in diff._lbl_dok.text()

    def test_diff_render_different(self, qapp: QApplication) -> None:
        h_a, h_b = _render_char_diff_html("123-ABC", "123-ABD")
        assert "background-color" in h_a
        assert "background-color" in h_b
        assert "C" in h_a
        assert "D" in h_b


class TestFileTableAndProxyModel:
    def test_table_model(self, qapp: QApplication) -> None:
        model = FileTableModel()
        item1 = HasilValidasiDokumen(
            nama_file="a.pdf",
            path_file="/a.pdf",
            status=StatusValidasi.VALID,
            skema_terpakai="S1",
            skor=8,
            skor_total=8,
        )
        item2 = HasilValidasiDokumen(
            nama_file="b.pdf",
            path_file="/b.pdf",
            status=StatusValidasi.TIDAK_VALID,
            skema_terpakai="S1",
            skor=4,
            skor_total=8,
            masalah=("Field tidak cocok",),
        )

        model.set_results([item1, item2])
        assert model.rowCount() == 2
        assert model.columnCount() == 4
        assert model.data(model.index(0, 0)) == "a.pdf"
        assert model.data(model.index(1, 3)) == "Field tidak cocok"

        # Proxy Filter
        proxy = FileFilterProxyModel()
        proxy.setSourceModel(model)
        assert proxy.rowCount() == 2

        # Filter status
        proxy.set_status_filter(StatusValidasi.TIDAK_VALID)
        assert proxy.rowCount() == 1
        assert proxy.data(proxy.index(0, 0)) == "b.pdf"

        # Search filter
        proxy.set_status_filter(None)
        proxy.set_search_filter("a.pdf")
        assert proxy.rowCount() == 1


class TestViews:
    def test_validation_view(self, qapp: QApplication) -> None:
        ps = ProfileService()
        rs = RecapService()
        vs = ValidationService()
        view = ValidationView(ps, rs, vs)
        assert view._combo_profil.count() >= 1

        # Mode change
        view._radio_single.setChecked(True)
        assert view._chk_subfolder.isHidden()
        view._radio_bulk.setChecked(True)
        assert not view._chk_subfolder.isHidden()

    def test_results_view(self, qapp: QApplication) -> None:
        view = ResultsView()
        item = HasilValidasiDokumen(
            nama_file="doc1.pdf",
            path_file="tests/data/pdf_benar.pdf",
            status=StatusValidasi.VALID,
            skema_terpakai="Skema A",
            skor=8,
            skor_total=8,
        )
        bulk = HasilBulk(
            hasil_per_file=(item,),
            folder_output="out",
            total=1,
            valid=1,
            tidak_valid=0,
            perlu_dicek=0,
            tidak_bisa_dibaca=0,
            waktu_mulai="",
            waktu_selesai="",
            versi_app="1.0.0",
            nama_profil="Profil",
            hash_profil="h",
            hash_rekap="r",
        )
        view.display_bulk_results(bulk)
        assert view._stat_valid._count == 1
        assert view._table_model.rowCount() == 1

    def test_main_window(self, qapp: QApplication) -> None:
        win = MainWindow()
        assert win._stacked.count() == 3

        # Nav switch
        win._switch_nav(2)
        assert win._stacked.currentIndex() == 2
        win._switch_nav(1)
        assert win._stacked.currentIndex() == 1
