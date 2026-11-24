@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo VALIDATOR DOKUMEN - Build Executable Windows (PyInstaller)
echo ============================================================

REM 1. Verifikasi Kode & Menjalankan Tes
echo [1/3] Menjalankan Quality Check (Ruff, Mypy, Pytest)...
call .\check.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Quality check gagal! Perbaiki error sebelum membangun executable.
    exit /b 1
)

REM 2. Bersihkan Folder Build & Dist Sebelumnya
echo [2/3] Membersihkan folder build dan dist lama...
if exist "build" rmdir /s /q "build"
if exist "dist\ValidatorDokumen" rmdir /s /q "dist\ValidatorDokumen"

REM 3. Eksekusi PyInstaller
echo [3/3] Membangun bundle aplikasi Windows mandiri...
pyinstaller --noconfirm --onedir --windowed ^
    --name "ValidatorDokumen" ^
    --add-data "validator_dokumen;validator_dokumen" ^
    --hidden-import "openpyxl" ^
    --hidden-import "pandas" ^
    --hidden-import "fitz" ^
    --hidden-import "pymupdf" ^
    --hidden-import "pdfplumber" ^
    --hidden-import "pytesseract" ^
    --hidden-import "cv2" ^
    --hidden-import "PIL" ^
    --hidden-import "numpy" ^
    --hidden-import "rapidfuzz" ^
    --hidden-import "pydantic" ^
    --hidden-import "PySide6" ^
    main.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build gagal!
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo BUILD BERHASIL!
echo Executable Windows siap digunakan di:
echo dist\ValidatorDokumen\ValidatorDokumen.exe
echo ============================================================
