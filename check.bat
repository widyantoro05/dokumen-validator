@echo off
REM check.bat - Jalankan ruff, mypy, dan pytest sekaligus
echo ============================================================
echo VALIDATOR DOKUMEN - Quality Check
echo ============================================================

cd /d "%~dp0"

echo.
echo [1/3] Ruff (lint + format check)...
python -m ruff check validator_dokumen/core validator_dokumen/services
if errorlevel 1 (
    echo GAGAL: ruff check menemukan masalah.
    exit /b 1
)
python -m ruff format --check validator_dokumen/core validator_dokumen/services
if errorlevel 1 (
    echo GAGAL: ruff format menemukan perbedaan.
    exit /b 1
)
echo OK: Ruff lulus.

echo.
echo [2/3] Mypy (type check)...
python -m mypy validator_dokumen/core validator_dokumen/services
if errorlevel 1 (
    echo GAGAL: mypy menemukan error tipe.
    exit /b 1
)
echo OK: Mypy lulus.

echo.
echo [3/3] Pytest (unit test + coverage)...
python -m pytest tests/ -v
if errorlevel 1 (
    echo GAGAL: ada tes yang tidak lulus.
    exit /b 1
)
echo OK: Semua tes lulus.

echo.
echo ============================================================
echo Semua pengecekan LULUS!
echo ============================================================
