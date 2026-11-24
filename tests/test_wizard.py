"""
tests/test_wizard.py - Pengujian Unit untuk Stepper Siapkan Profil 5 Langkah.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from validator_dokumen.core.models import (
    DefinisiField,
    ModeCocok,
    OpsiNormalisasi,
    PasanganPencocokan,
    PeranPasangan,
    ProfilValidasi,
    SkemaPencocokan,
)
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.ui.profile_wizard import ProfileWizard, StepperBar
from validator_dokumen.ui.steps.step1_recap import Step1Recap
from validator_dokumen.ui.steps.step2_field import FieldDialog, Step2Field
from validator_dokumen.ui.steps.step3_matching import PasanganDialog, Step3Matching
from validator_dokumen.ui.steps.step4_rules import (
    AturanFieldDialog,
    KondisiJikaMakaDialog,
    Step4Rules,
)
from validator_dokumen.ui.steps.step5_test_save import Step5TestSave


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app  # type: ignore[return-value]


class TestStepperBar:
    def test_stepper_bar(self, qapp: QApplication) -> None:
        bar = StepperBar(0)
        assert bar._current_step == 0
        bar.set_current_step(2)
        assert bar._current_step == 2
        assert bar._buttons[2].isChecked()


class TestStep1Recap:
    def test_step1_load_excel(self, qapp: QApplication, tmp_path: Path) -> None:
        rs = RecapService()
        step = Step1Recap(rs)
        assert not step.is_valid_step()

        excel_path = "tests/data/rekapan.xlsx"
        if Path(excel_path).exists():
            step._edit_path.setText(excel_path)
            step._muat_rekap()
            assert step.is_valid_step()
            assert step.dapatkan_tabel_rekap() is not None
            assert step._table_model.rowCount() > 0
            assert step._stats_model.rowCount() > 0


class TestStep2Field:
    def test_step2_fields(self, qapp: QApplication) -> None:
        step = Step2Field()
        assert not step.is_valid_step()

        field1 = DefinisiField(
            id="f1",
            nama="nomor_izin",
            cara_ambil="label",
            parameter={"label": ["Nomor Izin", "No:"]},
            wajib=True,
        )
        step.set_fields_and_pdfs([field1], ["tests/data/pdf_benar.pdf"])
        assert step.is_valid_step()
        assert len(step.dapatkan_fields()) == 1

        # Test field dialog
        dlg = FieldDialog(field1)
        assert dlg._edit_nama.text() == "nomor_izin"
        res = dlg.get_definisi_field()
        assert res.nama == "nomor_izin"


class TestStep3Matching:
    def test_step3_matching(self, qapp: QApplication) -> None:
        rs = RecapService()
        tabel = rs.muat_tabel_rekap(Path("tests/data/rekapan.xlsx"))
        kolom_nama = list(tabel.kolom)[0]
        field1 = DefinisiField(id="f1", nama="nomor_izin", cara_ambil="label", parameter={"label": ["No:"]})
        field2 = DefinisiField(id="f2", nama="nama_perusahaan", cara_ambil="label", parameter={"label": ["PT:"]})

        step = Step3Matching()
        step.set_context(tabel, [field1, field2])
        assert not step.is_valid_step()

        # Tambahkan pasangan KUNCI
        p_kunci = PasanganPencocokan(
            id="p1",
            kolom_rekap=kolom_nama,
            field_dokumen="nomor_izin",
            peran=PeranPasangan.KUNCI,
            mode=ModeCocok.PERSIS_NORMALISASI,
            normalisasi=OpsiNormalisasi(),
        )
        skema = SkemaPencocokan(
            id="s1",
            nama="Skema Utama",
            pasangan=(p_kunci,),
            k_minimum=1,
        )
        step.set_context(tabel, [field1, field2], [skema])
        assert step.is_valid_step()
        assert len(step.dapatkan_skema_list()) == 1

        # Test dialog pasangan
        dlg = PasanganDialog(list(tabel.kolom), ["nomor_izin", "nama_perusahaan"], p_kunci)
        res = dlg.get_pasangan()
        assert res.kolom_rekap == kolom_nama


class TestStep4Rules:
    def test_step4_rules(self, qapp: QApplication) -> None:
        step = Step4Rules()
        assert step.is_valid_step()

        # Test AturanFieldDialog
        dlg_af = AturanFieldDialog(["nomor_izin", "tanggal_terbit"])
        dlg_af._edit_param1.setText(r"^\d+$")
        af = dlg_af.get_aturan()
        assert af.field_nama == "nomor_izin"

        # Test KondisiJikaMakaDialog
        dlg_jm = KondisiJikaMakaDialog(["kategori"], ["nomor_izin"])
        km = dlg_jm.get_kondisi()
        assert km.id is not None


class TestStep5TestSave:
    def test_step5_test_and_save(self, qapp: QApplication, tmp_path: Path) -> None:
        ps = ProfileService(folder=tmp_path / "profiles")
        rs = RecapService()
        vs = ValidationService()

        tabel = rs.muat_tabel_rekap(Path("tests/data/rekapan.xlsx"))
        kolom_nama = list(tabel.kolom)[0]
        field = DefinisiField(id="f1", nama="nomor_izin", cara_ambil="label", parameter={"label": ["Nomor Izin:"]})
        p = PasanganPencocokan(
            id="p1",
            kolom_rekap=kolom_nama,
            field_dokumen="nomor_izin",
            peran=PeranPasangan.KUNCI,
            mode=ModeCocok.PERSIS_NORMALISASI,
            normalisasi=OpsiNormalisasi(),
        )
        skema = SkemaPencocokan(id="s1", nama="Skema Utama", pasangan=(p,), k_minimum=1)

        step = Step5TestSave(ps, vs)
        step.set_context(
            tabel_rekap=tabel,
            contoh_pdfs=["tests/data/pdf_benar.pdf"],
            fields=[field],
            skema_list=[skema],
            aturan_field=[],
            kondisi_list=[],
            profil_id="prof_test_step5",
            profil_nama="Profil Uji Step 5",
        )

        assert step.is_valid_step()

        # Jalankan pengujian
        step._jalankan_uji()
        assert step._table_model.rowCount() == 1

        # Simpan profil
        step._simpan_profil()
        assert ps.dapatkan_profil("prof_test_step5") is not None

    def test_wizard_navigation_and_sync(self, qapp: QApplication, tmp_path: Path) -> None:
        ps = ProfileService(folder=tmp_path / "profiles")
        rs = RecapService()
        vs = ValidationService()

        wiz = ProfileWizard(ps, rs, vs)
        assert wiz._stacked.currentIndex() == 0

        # Muat rekapan ke step 1
        wiz._step1._edit_path.setText("tests/data/rekapan.xlsx")
        wiz._step1._muat_rekap()
        assert wiz._step1.is_valid_step()

        # Maju ke step 2
        wiz._next_step()
        assert wiz._stacked.currentIndex() == 1

        # Tambah field di step 2
        field = DefinisiField(id="f1", nama="nomor_izin", cara_ambil="label", parameter={"label": ["Nomor:"]})
        wiz._step2.set_fields_and_pdfs([field], ["tests/data/pdf_benar.pdf"])
        assert wiz._step2.is_valid_step()

        # Maju ke step 3
        wiz._next_step()
        assert wiz._stacked.currentIndex() == 2

        # Muat profil yang sudah ada
        dummy = ProfilValidasi(
            schema_version=1,
            id="p_default",
            nama="Profil Default",
            deskripsi="",
            field_dokumen=(field,),
            skema_pencocokan=(),
            aturan_field=(),
            kondisi_jika_maka=(),
        )
        ps.simpan(dummy)
        p_obj = ps.dapatkan_profil("p_default")
        assert p_obj is not None
        wiz.muat_profil(p_obj)
        assert wiz._profil_id == p_obj.id
