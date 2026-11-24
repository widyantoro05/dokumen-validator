"""
core/output_writer.py - Penulis output hasil validasi bulk.

Struktur output:
  hasil_validasi_YYYYMMDD_HHMMSS/
    valid/
    not_valid/
      catatan_kesalahan.txt
      catatan_kesalahan.xlsx
    ringkasan.xlsx
    rekapan_tidak_terpakai.xlsx
    log_audit.txt

Semua penulisan atomik (tulis ke .tmp lalu rename).
"""

from __future__ import annotations

import contextlib
import shutil
from datetime import datetime
from pathlib import Path

from validator_dokumen.core.constants import OUTPUT_DATE_FORMAT, OUTPUT_ENCODING
from validator_dokumen.core.models import (
    HasilBulk,
    HasilValidasiDokumen,
    StatusValidasi,
    TabelRekap,
)


def _nama_folder_output(waktu: datetime | None = None) -> str:
    """Buat nama folder output berdasarkan waktu."""
    t = waktu or datetime.now()
    return f"hasil_validasi_{t.strftime(OUTPUT_DATE_FORMAT)}"


def _salin_atau_pindah_file(
    sumber: Path,
    tujuan: Path,
    pindah: bool = False,
) -> None:
    """
    Salin atau pindah file. Tangani nama bentrok dengan menambahkan _1, _2, dll.
    """
    tujuan.parent.mkdir(parents=True, exist_ok=True)

    # Tangani nama bentrok
    if tujuan.exists():
        batang = tujuan.stem
        ekstensi = tujuan.suffix
        counter = 1
        while tujuan.exists():
            tujuan = tujuan.parent / f"{batang}_{counter}{ekstensi}"
            counter += 1

    if pindah:
        shutil.move(str(sumber), str(tujuan))
    else:
        shutil.copy2(str(sumber), str(tujuan))


def _tulis_atomik(path: Path, konten: str, encoding: str = OUTPUT_ENCODING) -> None:
    """Tulis file secara atomik: tulis ke .tmp lalu rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path_tmp = path.with_suffix(".tmp")
    path_tmp.write_text(konten, encoding=encoding)
    path_tmp.replace(path)


def _tulis_catatan_txt(
    folder_not_valid: Path,
    hasil_list: list[HasilValidasiDokumen],
) -> None:
    """Tulis catatan_kesalahan.txt per file gagal."""
    baris: list[str] = []

    if not hasil_list:
        baris.append("Tidak ada kesalahan.\n")
        _tulis_atomik(folder_not_valid / "catatan_kesalahan.txt", "\n".join(baris))
        return

    for hasil in hasil_list:
        baris.append(f"File: {hasil.nama_file}")
        status_label = {
            StatusValidasi.TIDAK_VALID: "TIDAK VALID",
            StatusValidasi.PERLU_DICEK: "PERLU DICEK MANUAL",
            StatusValidasi.TIDAK_BISA_DIBACA: f"TIDAK BISA DIBACA: {hasil.error_teknis}",
        }.get(hasil.status, hasil.status.value)

        baris.append(
            f"  Status: {status_label} | Skema: {hasil.skema_terpakai or '-'} | Skor: {hasil.skor}/{hasil.skor_total}"
        )

        if hasil.baris_rekap_nomor:
            baris.append(
                f'  Baris rekapan acuan: {hasil.file_rekap}, sheet "{hasil.sheet_rekap}", baris {hasil.baris_rekap_nomor}'
            )

        for masalah in hasil.masalah:
            baris.append(f"  - {masalah}")

        # Detail dari hasil skema
        for hs in hasil.hasil_skema:
            if hs.baris_rekap_id:
                for hp in hs.pasangan_hasil:
                    if not hp.cocok:
                        sumber_info = ""
                        for nf in hasil.hasil_field:
                            if nf.nama_field == hp.field_dokumen:
                                sumber_info = f" (hal. {nf.halaman}, sumber: {nf.sumber.value}, conf {nf.confidence:.0f}%)"
                                break
                        baris.append(f"  - [{hp.field_dokumen}] {hp.pesan_kesalahan}{sumber_info}")

        baris.append("----")

    _tulis_atomik(folder_not_valid / "catatan_kesalahan.txt", "\n".join(baris))


def _tulis_catatan_xlsx(
    folder_not_valid: Path,
    hasil_list: list[HasilValidasiDokumen],
) -> None:
    """Tulis catatan_kesalahan.xlsx dengan format tabel."""
    try:
        import openpyxl  # type: ignore[import-untyped]
        from openpyxl.styles import Font, PatternFill  # type: ignore[import-untyped]
    except ImportError:
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Catatan Kesalahan"

    header = [
        "Nama File",
        "Status",
        "Skema",
        "Skor",
        "File Rekapan",
        "Sheet",
        "Baris Rekapan",
        "Field/Kolom",
        "Kesalahan",
        "Nilai Dokumen",
        "Nilai Rekapan",
        "Halaman",
        "Sumber",
        "Confidence",
    ]
    ws.append(header)

    # Style header
    font_bold = Font(bold=True)
    for cell in ws[1]:
        cell.font = font_bold
        cell.fill = PatternFill(fill_type="solid", fgColor="D3D3D3")

    # Warna per status
    warna_status = {
        StatusValidasi.TIDAK_VALID: "FEE2E2",
        StatusValidasi.PERLU_DICEK: "FEF3C7",
        StatusValidasi.TIDAK_BISA_DIBACA: "E2E8F0",
    }

    for hasil in hasil_list:
        warna = warna_status.get(hasil.status, "FFFFFF")
        fill = PatternFill(fill_type="solid", fgColor=warna)

        def tambah_baris(
            field_nama: str = "",
            kesalahan: str = "",
            nilai_dok: str = "",
            nilai_rek: str = "",
            halaman: str = "",
            sumber_str: str = "",
            conf: str = "",
        ) -> None:
            baris_data = [
                hasil.nama_file,
                hasil.status.value,
                hasil.skema_terpakai or "-",
                f"{hasil.skor}/{hasil.skor_total}",
                hasil.file_rekap,
                hasil.sheet_rekap,
                str(hasil.baris_rekap_nomor) if hasil.baris_rekap_nomor else "-",
                field_nama,
                kesalahan,
                nilai_dok,
                nilai_rek,
                halaman,
                sumber_str,
                conf,
            ]
            ws.append(baris_data)
            for cell in ws[ws.max_row]:
                cell.fill = fill

        # Jika tidak bisa dibaca
        if hasil.status == StatusValidasi.TIDAK_BISA_DIBACA:
            tambah_baris(kesalahan=hasil.error_teknis)
            continue

        # Detail pasangan yang tidak cocok
        ada_detail = False
        for hs in hasil.hasil_skema:
            if hs.baris_rekap_id:
                for hp in hs.pasangan_hasil:
                    if not hp.cocok:
                        # Cari info OCR
                        hal = ""
                        sumber_str = ""
                        conf = ""
                        for nf in hasil.hasil_field:
                            if nf.nama_field == hp.field_dokumen:
                                hal = str(nf.halaman)
                                sumber_str = nf.sumber.value
                                conf = f"{nf.confidence:.0f}%"
                                break
                        tambah_baris(
                            field_nama=hp.field_dokumen,
                            kesalahan=hp.pesan_kesalahan,
                            nilai_dok=hp.nilai_dokumen,
                            nilai_rek=hp.nilai_rekap,
                            halaman=hal,
                            sumber_str=sumber_str,
                            conf=conf,
                        )
                        ada_detail = True

        if not ada_detail:
            for masalah in hasil.masalah:
                tambah_baris(kesalahan=masalah)

    # Auto lebar kolom
    for kolom in ws.columns:
        max_len = 0
        col_letter = kolom[0].column_letter
        for cell in kolom:
            with contextlib.suppress(Exception):
                max_len = max(max_len, len(str(cell.value or "")))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    # Freeze header dan filter
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    path_xlsx = folder_not_valid / "catatan_kesalahan.xlsx"
    path_tmp = path_xlsx.with_suffix(".tmp")
    wb.save(str(path_tmp))
    path_tmp.replace(path_xlsx)


def _tulis_ringkasan_xlsx(
    folder_output: Path,
    hasil_bulk: HasilBulk,
) -> None:
    """Tulis ringkasan.xlsx: semua file + status + metadata reproduksi."""
    try:
        import openpyxl  # type: ignore[import-untyped]
        from openpyxl.styles import Font, PatternFill  # type: ignore[import-untyped]
    except ImportError:
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ringkasan"

    # Header
    header = [
        "Nama File",
        "Status",
        "Skor",
        "Skema Terpakai",
        "Baris Rekapan",
        "File Rekapan",
        "Sheet",
        "Waktu Proses (detik)",
    ]
    ws.append(header)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(fill_type="solid", fgColor="D3D3D3")

    warna_status = {
        StatusValidasi.VALID: "DCFCE7",
        StatusValidasi.TIDAK_VALID: "FEE2E2",
        StatusValidasi.PERLU_DICEK: "FEF3C7",
        StatusValidasi.TIDAK_BISA_DIBACA: "E2E8F0",
    }

    for hasil in hasil_bulk.hasil_per_file:
        warna = warna_status.get(hasil.status, "FFFFFF")
        ws.append(
            [
                hasil.nama_file,
                hasil.status.value,
                f"{hasil.skor}/{hasil.skor_total}",
                hasil.skema_terpakai or "-",
                str(hasil.baris_rekap_nomor) if hasil.baris_rekap_nomor else "-",
                hasil.file_rekap,
                hasil.sheet_rekap,
                f"{hasil.waktu_proses_detik:.2f}",
            ]
        )
        for cell in ws[ws.max_row]:
            cell.fill = PatternFill(fill_type="solid", fgColor=warna)

    # Sheet metadata reproduksi
    ws_meta = wb.create_sheet("Metadata Reproduksi")
    meta_rows = [
        ("Versi Aplikasi", hasil_bulk.versi_app),
        ("Nama Profil", hasil_bulk.nama_profil),
        ("Hash Profil", hasil_bulk.hash_profil),
        ("Hash Rekapan", hasil_bulk.hash_rekap),
        ("Waktu Mulai", hasil_bulk.waktu_mulai),
        ("Waktu Selesai", hasil_bulk.waktu_selesai),
        ("Total File", str(hasil_bulk.total)),
        ("Valid", str(hasil_bulk.valid)),
        ("Tidak Valid", str(hasil_bulk.tidak_valid)),
        ("Perlu Dicek", str(hasil_bulk.perlu_dicek)),
        ("Tidak Bisa Dibaca", str(hasil_bulk.tidak_bisa_dibaca)),
    ]
    for baris in meta_rows:
        ws_meta.append(list(baris))

    for kolom in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in kolom), default=10)
        ws.column_dimensions[kolom[0].column_letter].width = min(max_len + 4, 60)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    path = folder_output / "ringkasan.xlsx"
    path_tmp = path.with_suffix(".tmp")
    wb.save(str(path_tmp))
    path_tmp.replace(path)


def _tulis_rekap_tidak_terpakai(
    folder_output: Path,
    tabel_rekap: TabelRekap | None,
    id_baris_terpakai: set[str],
) -> None:
    """Tulis rekapan_tidak_terpakai.xlsx: baris yang tidak punya dokumen pasangan."""
    try:
        import openpyxl  # type: ignore[import-untyped]
        from openpyxl.styles import Font  # type: ignore[import-untyped]
    except ImportError:
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rekapan Tidak Terpakai"

    if tabel_rekap is None or not tabel_rekap.baris:
        ws.append(["Tidak ada data rekapan yang dimuat."])
        wb.save(str(folder_output / "rekapan_tidak_terpakai.xlsx"))
        return

    # Header
    header = [*list(tabel_rekap.kolom), "Nomor Baris Asli", "Sumber File", "Sheet"]
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for baris in tabel_rekap.baris:
        if baris.id not in id_baris_terpakai:
            baris_data = [baris.data.get(k, "") for k in tabel_rekap.kolom]
            baris_data += [str(baris.nomor_baris_asli), baris.sumber_file, baris.sumber_sheet]
            ws.append(baris_data)

    path = folder_output / "rekapan_tidak_terpakai.xlsx"
    path_tmp = path.with_suffix(".tmp")
    wb.save(str(path_tmp))
    path_tmp.replace(path)


def tulis_output_bulk(
    hasil_bulk: HasilBulk,
    folder_input: Path,
    tabel_rekap: TabelRekap | None = None,
    pindah: bool = False,
) -> Path:
    """
    Tulis semua output bulk ke folder hasil.

    Args:
        hasil_bulk: Hasil validasi bulk.
        folder_input: Folder sumber file PDF (output di samping folder ini).
        tabel_rekap: Tabel rekapan untuk laporan tidak terpakai.
        pindah: Jika True, pindah file (default: salin).

    Returns:
        Path folder output yang dibuat.
    """
    folder_output = folder_input.parent / hasil_bulk.folder_output
    folder_output.mkdir(parents=True, exist_ok=True)

    folder_valid = folder_output / "valid"
    folder_not_valid = folder_output / "not_valid"
    folder_valid.mkdir(exist_ok=True)
    folder_not_valid.mkdir(exist_ok=True)

    hasil_gagal: list[HasilValidasiDokumen] = []
    id_baris_terpakai: set[str] = set()

    # Kelompokkan dan salin file
    for hasil in hasil_bulk.hasil_per_file:
        path_file = Path(hasil.path_file)

        if hasil.status == StatusValidasi.VALID:
            if path_file.exists():
                _salin_atau_pindah_file(path_file, folder_valid / hasil.nama_file, pindah)
        else:
            hasil_gagal.append(hasil)
            if path_file.exists():
                _salin_atau_pindah_file(path_file, folder_not_valid / hasil.nama_file, pindah)

        # Catat baris rekapan yang terpakai
        for hs in hasil.hasil_skema:
            if hs.baris_rekap_id:
                id_baris_terpakai.add(hs.baris_rekap_id)

    # Tulis catatan kesalahan
    _tulis_catatan_txt(folder_not_valid, hasil_gagal)
    _tulis_catatan_xlsx(folder_not_valid, hasil_gagal)

    # Tulis ringkasan
    _tulis_ringkasan_xlsx(folder_output, hasil_bulk)

    # Tulis rekapan tidak terpakai
    _tulis_rekap_tidak_terpakai(folder_output, tabel_rekap, id_baris_terpakai)

    return folder_output
