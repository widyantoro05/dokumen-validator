"""
tools/screenshot.py - Skrip otomatis penangkap layar aplikasi Validator Dokumen.

Menghasilkan pratinjau PNG dari setiap layar untuk dokumentasi tanpa perlu interaksi manual:
1. docs/screens/01_validasi.png
2. docs/screens/02_hasil.png
3. docs/screens/03_wizard_step1_rekap.png
4. docs/screens/04_wizard_step2_field.png
5. docs/screens/05_wizard_step3_matching.png
6. docs/screens/06_wizard_step4_rules.png
7. docs/screens/07_wizard_step5_simpan.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Tambahkan direktori root proyek ke sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set environment offscreen jika diperlukan
os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from PySide6.QtWidgets import QApplication
from validator_dokumen.core.constants import APP_VERSION
from validator_dokumen.core.models import (
    HasilBulk,
    HasilPasangan,
    HasilSkema,
    HasilValidasiDokumen,
    LangkahJejak,
    StatusValidasi,
)
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.ui.main_window import MainWindow
from validator_dokumen.ui.theme import generate_qss


def main() -> None:
    output_dir = Path("docs/screens")
    output_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        app.setApplicationName("Validator Dokumen")
        app.setStyleSheet(generate_qss())

    ps = ProfileService()

    # Pastikan data contoh ada
    rekap_path = Path("contoh_data/rekapan.xlsx")
    pdf_sample = Path("contoh_data/pdf_benar.pdf")
    if not rekap_path.exists() or not pdf_sample.exists():
        from tools.buat_data_contoh import main as buat_data_contoh_main

        buat_data_contoh_main()

    # Pastikan profil contoh dimuat
    if not ps.daftar_profil():
        ps.buat_profil_contoh()

    win = MainWindow()
    win.resize(1180, 800)
    win.show()
    app.processEvents()

    # 1. Layar Validasi
    win._switch_nav(1)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "01_validasi.png"))
    print("✓ Tersimpan: docs/screens/01_validasi.png")

    # 2. Layar Hasil dengan Dummy Data Realistis
    win._switch_nav(2)
    sample_items = [
        HasilValidasiDokumen(
            nama_file="izin_01_pt_maju_berkah.pdf",
            path_file=str(Path("contoh_data/pdf/izin_01.pdf").resolve()),
            status=StatusValidasi.VALID,
            skema_terpakai="Skema Utama (NIB + Nama)",
            skor=6,
            skor_total=6,
            baris_rekap_nomor=2,
            masalah=(),
            jejak_keputusan=(
                LangkahJejak(
                    langkah="Kunci NIB", keterangan="NIB 1234567890123 cocok persis", hasil=True
                ),
                LangkahJejak(
                    langkah="Pembanding Nama",
                    keterangan="Nama PT MAJU BERKAH cocok persis",
                    hasil=True,
                ),
            ),
            hasil_skema=(
                HasilSkema(
                    skema_id="skema_1",
                    skema_nama="Skema Utama",
                    baris_rekap_id="row_1",
                    baris_rekap_nomor=2,
                    skor=6,
                    skor_total=6,
                    status=StatusValidasi.VALID,
                    pasangan_hasil=(
                        HasilPasangan(
                            pasangan_id="p1",
                            kolom_rekap="nib",
                            field_dokumen="nib",
                            nilai_dokumen="1234567890123",
                            nilai_rekap="1234567890123",
                            cocok=True,
                            skor_mirip=None,
                            meragukan=False,
                            jejak=(),
                        ),
                        HasilPasangan(
                            pasangan_id="p2",
                            kolom_rekap="nama_perusahaan",
                            field_dokumen="nama_perusahaan",
                            nilai_dokumen="PT MAJU BERKAH",
                            nilai_rekap="PT MAJU BERKAH",
                            cocok=True,
                            skor_mirip=None,
                            meragukan=False,
                            jejak=(),
                        ),
                    ),
                ),
            ),
        ),
        HasilValidasiDokumen(
            nama_file="izin_02_cv_sentosa_abadi.pdf",
            path_file=str(Path("contoh_data/pdf/izin_02.pdf").resolve()),
            status=StatusValidasi.TIDAK_VALID,
            skema_terpakai=None,
            skor=2,
            skor_total=6,
            masalah=("NIB tidak ditemukan di seluruh baris rekapan acuan.",),
        ),
        HasilValidasiDokumen(
            nama_file="izin_03_pt_kreatif_teknologi.pdf",
            path_file=str(Path("contoh_data/pdf/izin_03.pdf").resolve()),
            status=StatusValidasi.PERLU_DICEK,
            skema_terpakai="Skema Utama",
            skor=4,
            skor_total=6,
            masalah=("Kemiripan nama 82% (kandidat: 'PT KREATIF TEKNOLOGI JAYA').",),
        ),
        HasilValidasiDokumen(
            nama_file="izin_04_dokumen_rusak.pdf",
            path_file=str(Path("contoh_data/pdf/izin_04.pdf").resolve()),
            status=StatusValidasi.TIDAK_BISA_DIBACA,
            skema_terpakai=None,
            skor=0,
            skor_total=0,
            masalah=("Halaman kosong atau kualitas pemindaian di bawah ambang batas minimum.",),
            error_teknis="Halaman dokumen tidak terbaca / kosong",
        ),
    ]
    bulk_result = HasilBulk(
        hasil_per_file=tuple(sample_items),
        folder_output=str(Path("contoh_data/hasil_validasi").resolve()),
        total=4,
        valid=1,
        tidak_valid=1,
        perlu_dicek=1,
        tidak_bisa_dibaca=1,
        waktu_mulai="2026-11-24 10:00:00",
        waktu_selesai="2026-11-24 10:00:03",
        versi_app=APP_VERSION,
        nama_profil="Profil Contoh - Izin Usaha",
        hash_profil="abcdef1234567890",
        hash_rekap="0987654321fedcba",
    )
    win._view_hasil.display_bulk_results(bulk_result)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "02_hasil.png"))
    print("✓ Tersimpan: docs/screens/02_hasil.png")

    # Muat profil contoh ke wizard agar field dan skema terisi lengkap
    profil_list = ps.daftar_profil()
    if profil_list:
        try:
            profil_aktif = ps.muat(profil_list[0][2])
            win._wizard.muat_profil(profil_aktif)
        except Exception:
            pass

    # 3. Wizard Step 1: Rekapan
    win._switch_nav(0)
    win._wizard._stacked.setCurrentIndex(0)
    win._wizard._stepper_bar.set_current_step(0)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "03_wizard_step1_rekap.png"))
    print("✓ Tersimpan: docs/screens/03_wizard_step1_rekap.png")

    # 4. Wizard Step 2: Field
    win._wizard._stacked.setCurrentIndex(1)
    win._wizard._stepper_bar.set_current_step(1)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "04_wizard_step2_field.png"))
    print("✓ Tersimpan: docs/screens/04_wizard_step2_field.png")

    # 5. Wizard Step 3: Pencocokan
    win._wizard._stacked.setCurrentIndex(2)
    win._wizard._stepper_bar.set_current_step(2)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "05_wizard_step3_matching.png"))
    print("✓ Tersimpan: docs/screens/05_wizard_step3_matching.png")

    # 6. Wizard Step 4: Rules JIKA-MAKA
    win._wizard._stacked.setCurrentIndex(3)
    win._wizard._stepper_bar.set_current_step(3)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "06_wizard_step4_rules.png"))
    print("✓ Tersimpan: docs/screens/06_wizard_step4_rules.png")

    # 7. Wizard Step 5: Simpan & Ekspor
    win._wizard._stacked.setCurrentIndex(4)
    win._wizard._stepper_bar.set_current_step(4)
    app.processEvents()
    pix = win.grab()
    pix.save(str(output_dir / "07_wizard_step5_simpan.png"))
    print("✓ Tersimpan: docs/screens/07_wizard_step5_simpan.png")

    print("\nSemua screenshot berhasil dibuat di direktori docs/screens/!")


if __name__ == "__main__":
    main()
