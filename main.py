"""
main.py - Titik masuk (entry point) aplikasi desktop "Validator Dokumen".

Catatan Penting:
- Panggil multiprocessing.freeze_support() di baris paling awal agar aman saat di-bundle PyInstaller.
- Tangani exception tak terduga dengan global exception handler.
- Terapkan stylesheet QSS dari token tema.
"""

import multiprocessing

# WAJIB: freeze_support() di baris pertama sebelum import lain untuk keamanan PyInstaller
multiprocessing.freeze_support()

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from validator_dokumen.ui.main_window import MainWindow
from validator_dokumen.ui.theme import generate_qss
from validator_dokumen.utils.logger import log, setup_global_exception_handler


def main() -> None:
    # Pasang penangan exception global
    setup_global_exception_handler(log)

    # Inisialisasi Aplikasi Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Validator Dokumen")
    app.setOrganizationName("ValidatorDokumen")

    # Font Baku: Segoe UI
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Terapkan Stylesheet Terpusat dari Theme
    stylesheet = generate_qss()
    app.setStyleSheet(stylesheet)

    # Buat dan Tampilkan Jendela Utama
    window = MainWindow()
    window.show()

    log.info("Aplikasi Validator Dokumen dimulai.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
