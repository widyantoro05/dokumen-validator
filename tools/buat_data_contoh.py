"""
tools/buat_data_contoh.py - Generator data contoh untuk tes.

Membuat:
1. rekapan.xlsx - 200 baris, 8+ kolom
2. PDF teks yang benar (cocok semua field)
3. PDF salah (nomor beda, nama beda, kedaluwarsa)
4. PDF gambar (gambar dengan noise)
5. PDF rusak
6. PDF dengan kunci kembar
7. PDF hanya cocok 6 dari 8

Jalankan: python tools/buat_data_contoh.py
"""

from __future__ import annotations

import random
import string
import sys
from datetime import date, timedelta
from pathlib import Path

# Tambahkan root proyek ke path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _acak_str(panjang: int = 6) -> str:
    """Buat string acak huruf kapital."""
    return "".join(random.choices(string.ascii_uppercase, k=panjang))


def _acak_angka(panjang: int = 5) -> str:
    """Buat string angka acak."""
    return "".join(random.choices(string.digits, k=panjang))


def _format_tanggal(d: date) -> str:
    """Format tanggal ke dd/mm/yyyy."""
    return d.strftime("%d/%m/%Y")


def buat_rekapan(folder: Path, jumlah: int = 200) -> Path:
    """
    Buat file rekapan Excel dengan data acak.

    Args:
        folder: Folder output.
        jumlah: Jumlah baris data (selain header).

    Returns:
        Path file yang dibuat.
    """
    try:
        import openpyxl  # type: ignore[import-untyped]
        from openpyxl.styles import Font, PatternFill  # type: ignore[import-untyped]
    except ImportError:
        print("openpyxl tidak terinstal. Jalankan: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data Izin"

    # Header
    header = [
        "No Izin",
        "NIB",
        "Nama Perusahaan",
        "Jenis Usaha",
        "Alamat",
        "Tanggal Terbit",
        "Tanggal Berakhir",
        "NPWP",
        "Kota",
        "Provinsi",
    ]
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(fill_type="solid", fgColor="D3D3D3")

    jenis_usaha_list = [
        "Perdagangan Umum",
        "Jasa Konstruksi",
        "Industri Manufaktur",
        "Jasa Konsultansi",
        "Perdagangan Eceran",
        "Jasa Teknologi Informasi",
        "Industri Makanan",
        "Jasa Keuangan",
        "Perdagangan Grosir",
    ]
    kota_list = [
        ("Jakarta Selatan", "DKI Jakarta"),
        ("Surabaya", "Jawa Timur"),
        ("Bandung", "Jawa Barat"),
        ("Medan", "Sumatera Utara"),
        ("Makassar", "Sulawesi Selatan"),
        ("Semarang", "Jawa Tengah"),
        ("Yogyakarta", "DIY"),
        ("Palembang", "Sumatera Selatan"),
    ]
    prefix_badan = ["PT", "CV", "UD", "PD"]

    data_rows: list[list[str]] = []

    for _i in range(jumlah):
        no_izin = f"IZN-{_acak_angka(4)}-{_acak_str(3)}"
        nib = _acak_angka(13)
        prefix = random.choice(prefix_badan)
        nama = f"{prefix} {_acak_str(5).capitalize()} {_acak_str(4).capitalize()}"
        jenis = random.choice(jenis_usaha_list)
        kota, prov = random.choice(kota_list)
        alamat = f"Jl. {_acak_str(6).capitalize()} No. {random.randint(1, 999)}, {kota}"
        tgl_terbit = date(2020, 1, 1) + timedelta(days=random.randint(0, 1000))
        tgl_berakhir = tgl_terbit + timedelta(days=random.randint(365, 1825))
        npwp = f"{_acak_angka(2)}.{_acak_angka(3)}.{_acak_angka(3)}.{_acak_angka(1)}-{_acak_angka(3)}.{_acak_angka(3)}"

        baris = [
            no_izin,
            nib,
            nama,
            jenis,
            alamat,
            _format_tanggal(tgl_terbit),
            _format_tanggal(tgl_berakhir),
            npwp,
            kota,
            prov,
        ]
        data_rows.append(baris)
        ws.append(baris)

    # Lebar kolom otomatis
    for kolom in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in kolom)
        ws.column_dimensions[kolom[0].column_letter].width = min(max_len + 4, 50)

    ws.freeze_panes = "A2"

    path = folder / "rekapan.xlsx"
    wb.save(str(path))
    print(f"✔ Rekapan dibuat: {path} ({jumlah} baris)")
    return path, data_rows, header


def _buat_konten_pdf_teks(baris: list[str], header: list[str]) -> str:
    """Buat konten teks PDF dari satu baris rekapan."""
    data = dict(zip(header, baris, strict=False))
    return f"""SURAT IZIN USAHA
================

Nomor Izin: {data.get("No Izin", "")}

Data Perusahaan:
  Nama Perusahaan: {data.get("Nama Perusahaan", "")}
  NIB: {data.get("NIB", "")}
  NPWP: {data.get("NPWP", "")}
  Jenis Usaha: {data.get("Jenis Usaha", "")}
  Alamat: {data.get("Alamat", "")}

Tanggal diterbitkan: {data.get("Tanggal Terbit", "")}
Berlaku hingga: {data.get("Tanggal Berakhir", "")}

Diterbitkan oleh: Dinas Penanaman Modal dan PTSP
Stempel dan Tanda Tangan
"""


def buat_pdf_teks(
    folder: Path,
    nama_file: str,
    konten: str,
) -> Path:
    """Buat PDF teks dengan konten yang diberikan menggunakan PyMuPDF."""
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        print("PyMuPDF tidak terinstal. Jalankan: pip install PyMuPDF")
        sys.exit(1)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Tulis teks ke halaman
    baris_list = konten.strip().split("\n")
    y = 72
    for baris in baris_list:
        if baris.strip():
            page.insert_text(
                point=(72, y),
                text=baris,
                fontsize=11,
                fontname="helv",
            )
        y += 16

    path = folder / nama_file
    doc.save(str(path))
    doc.close()
    print(f"✔ PDF dibuat: {path}")
    return path


def buat_pdf_rusak(folder: Path) -> Path:
    """Buat file PDF yang rusak (konten tidak valid)."""
    path = folder / "pdf_rusak.pdf"
    path.write_bytes(b"%PDF-1.4\n% Ini bukan PDF yang valid\nINI RUSAK\n")
    print(f"✔ PDF rusak dibuat: {path}")
    return path


def buat_pdf_gambar(folder: Path, konten: str) -> Path:
    """
    Buat PDF yang berisi gambar (bukan teks langsung).
    Render teks ke gambar, lalu masukkan ke PDF.
    """
    try:
        import fitz  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]
        from PIL import Image, ImageDraw  # type: ignore[import-untyped]
    except ImportError:
        print("⚠ PIL/numpy tidak tersedia, membuat PDF teks sebagai fallback untuk gambar")
        return buat_pdf_teks(folder, "pdf_gambar.pdf", konten)

    # Buat gambar teks
    lebar, tinggi = 595, 842
    img = Image.new("RGB", (lebar, tinggi), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Tambahkan sedikit noise
    pixels = np.array(img)
    noise = np.random.randint(-10, 10, pixels.shape, dtype=np.int16)
    pixels = np.clip(pixels.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(pixels)
    draw = ImageDraw.Draw(img)

    # Tulis teks
    baris_list = konten.strip().split("\n")
    y = 72
    for baris in baris_list:
        draw.text((72, y), baris, fill=(0, 0, 0))
        y += 20

    # Konversi ke PDF
    path_png = folder / "temp_gambar.png"
    img.save(str(path_png))

    doc = fitz.open()
    page = doc.new_page(width=lebar, height=tinggi)
    page.insert_image(page.rect, filename=str(path_png))

    path = folder / "pdf_gambar.pdf"
    doc.save(str(path))
    doc.close()
    path_png.unlink(missing_ok=True)
    print(f"✔ PDF gambar dibuat: {path}")
    return path


def main() -> None:
    """Buat semua data contoh."""
    folder = ROOT / "tests" / "data"
    folder.mkdir(parents=True, exist_ok=True)

    random.seed(42)  # Deterministik

    # 1. Buat rekapan
    _path_rekap, data_rows, header = buat_rekapan(folder)

    # Ambil beberapa baris untuk buat PDF
    baris_benar = data_rows[0]  # Baris pertama: semua benar
    baris_salah = data_rows[1]  # Baris kedua: akan dimodifikasi
    baris_kembar = data_rows[2]  # Untuk kembar

    # 2. PDF benar (semua cocok)
    konten_benar = _buat_konten_pdf_teks(baris_benar, header)
    buat_pdf_teks(folder, "pdf_benar.pdf", konten_benar)

    # 3. PDF salah nomor izin
    baris_nomor_salah = list(baris_salah)
    baris_nomor_salah[0] = "IZN-XXXX-ZZZ"  # Nomor izin salah
    konten_nomor_salah = _buat_konten_pdf_teks(baris_nomor_salah, header)
    buat_pdf_teks(folder, "pdf_nomor_salah.pdf", konten_nomor_salah)

    # 4. PDF kedaluwarsa
    baris_kedaluwarsa = list(baris_salah)
    baris_kedaluwarsa[6] = "01/01/2020"  # Tanggal berakhir lampau
    konten_kedaluwarsa = _buat_konten_pdf_teks(baris_kedaluwarsa, header)
    buat_pdf_teks(folder, "pdf_kedaluwarsa.pdf", konten_kedaluwarsa)

    # 5. PDF hanya 6 dari 8 cocok (NPWP dan Tanggal Terbit beda)
    baris_6_dari_8 = list(baris_benar)
    baris_6_dari_8[7] = "00.000.000.0-000.000"  # NPWP beda
    baris_6_dari_8[5] = "01/01/2019"  # Tanggal terbit beda
    konten_6_dari_8 = _buat_konten_pdf_teks(baris_6_dari_8, header)
    buat_pdf_teks(folder, "pdf_6_dari_8.pdf", konten_6_dari_8)

    # 6. PDF gambar
    buat_pdf_gambar(folder, konten_benar)

    # 7. PDF rusak
    buat_pdf_rusak(folder)

    # 8. PDF kembar (kunci sama dengan baris lain)
    # Gunakan baris_benar tapi dengan NIB yang sama dengan baris_kembar
    baris_dengan_kembar = list(baris_kembar)
    baris_dengan_kembar[1] = baris_benar[1]  # Gunakan NIB baris pertama (duplikat)
    konten_kembar = _buat_konten_pdf_teks(baris_dengan_kembar, header)
    buat_pdf_teks(folder, "pdf_kembar.pdf", konten_kembar)

    print(f"\n✔ Semua data contoh dibuat di: {folder}")
    print("  File yang tersedia:")
    for f in sorted(folder.iterdir()):
        print(f"    {f.name} ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
