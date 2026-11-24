"""
cli.py - Antarmuka baris perintah (CLI) untuk Validator Dokumen.

Perintah yang tersedia:
  validasi  - Validasi satu PDF atau folder PDF
  profil    - Kelola profil (daftar, buat-contoh)

Semua logika validasi ada di services/ dan core/; CLI hanya tipis.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from validator_dokumen.core.models import StatusValidasi
from validator_dokumen.core.profile_schema import ProfilTidakValid
from validator_dokumen.services.profile_service import ProfileService
from validator_dokumen.services.recap_service import RecapService
from validator_dokumen.services.validation_service import ValidationService
from validator_dokumen.utils.logger import log


def cmd_validasi(args: argparse.Namespace) -> int:
    """
    Perintah validasi: satu PDF atau bulk folder.

    Returns:
        Exit code: 0 = semua valid, 1 = ada yang tidak valid, 2 = error.
    """
    path_profil = Path(args.profil)
    path_rekap = Path(args.rekap)
    path_input = Path(args.input)

    # Muat profil
    ps = ProfileService()
    try:
        profil = ps.muat(path_profil)
        print(f"✔ Profil dimuat: {profil.nama}")
    except (FileNotFoundError, ProfilTidakValid) as e:
        print(f"✖ Profil gagal dimuat: {e}", file=sys.stderr)
        return 2

    # Muat rekapan
    rs = RecapService()
    try:
        sheet_nama = getattr(args, "sheet", None)
        baris_header = getattr(args, "header", 1)
        tabel = rs.muat_excel(path_rekap, sheet_nama, baris_header)
        print(f"✔ Rekapan dimuat: {len(tabel.baris)} baris, {len(tabel.kolom)} kolom")
    except Exception as e:
        print(f"✖ Rekapan gagal dimuat: {e}", file=sys.stderr)
        return 2

    # Deteksi kolom hilang
    kolom_dibutuhkan: list[str] = []
    for skema in profil.skema_pencocokan:
        for pasangan in skema.pasangan:
            if pasangan.kolom_rekap not in kolom_dibutuhkan:
                kolom_dibutuhkan.append(pasangan.kolom_rekap)

    hilang = ps.deteksi_kolom_hilang(profil, list(tabel.kolom))
    if hilang:
        print("⚠ Peringatan: kolom rekapan berikut tidak ditemukan di file:")
        for h in hilang:
            print(f"   - [{h['skema_nama']}] '{h['kolom_rekap']}' (untuk field '{h['field_dokumen']}')")

    # Bangun indeks
    from validator_dokumen.core.models import OpsiNormalisasi
    opsi_per_kolom: dict[str, OpsiNormalisasi] = {}
    for skema in profil.skema_pencocokan:
        for pasangan in skema.pasangan:
            opsi_per_kolom[pasangan.kolom_rekap] = pasangan.normalisasi

    try:
        indeks = rs.bangun_indeks(kolom_dibutuhkan, opsi_per_kolom)
        print(f"✔ Indeks dibangun untuk {len(kolom_dibutuhkan)} kolom")
    except Exception as e:
        print(f"✖ Gagal membangun indeks: {e}", file=sys.stderr)
        return 2

    # Validasi
    vs = ValidationService()

    if path_input.is_file():
        # Single file
        print(f"\nValidasi: {path_input.name}")
        hasil = vs.validasi_satu(path_input, profil, indeks)
        _cetak_hasil_satu(hasil)
        return 0 if hasil.status == StatusValidasi.VALID else 1

    elif path_input.is_dir():
        # Bulk folder
        sertakan_subfolder = getattr(args, "subfolder", False)
        print(f"\nValidasi bulk: {path_input}")

        def progres(selesai: int, total: int, hasil: Any) -> None:  # type: ignore[name-defined]
            status_simbol = {
                StatusValidasi.VALID: "✔",
                StatusValidasi.TIDAK_VALID: "✖",
                StatusValidasi.PERLU_DICEK: "⚠",
                StatusValidasi.TIDAK_BISA_DIBACA: "⦸",
            }.get(hasil.status, "?")
            print(f"  [{selesai:3d}/{total}] {status_simbol} {hasil.nama_file}")

        try:
            hasil_bulk = vs.validasi_bulk(
                folder_pdf=path_input,
                profil=profil,
                indeks=indeks,
                tabel_rekap=tabel,
                sertakan_subfolder=sertakan_subfolder,
                callback_progres=progres,  # type: ignore[arg-type]
            )

            print(f"\n{'='*60}")
            print(f"HASIL VALIDASI BULK")
            print(f"  Total       : {hasil_bulk.total}")
            print(f"  Valid       : {hasil_bulk.valid}")
            print(f"  Tidak Valid : {hasil_bulk.tidak_valid}")
            print(f"  Perlu Dicek : {hasil_bulk.perlu_dicek}")
            print(f"  Tidak Terbaca: {hasil_bulk.tidak_bisa_dibaca}")
            print(f"  Output      : {path_input.parent / hasil_bulk.folder_output}")

            return 0 if hasil_bulk.tidak_valid == 0 and hasil_bulk.perlu_dicek == 0 else 1

        except ValueError as e:
            print(f"✖ Error: {e}", file=sys.stderr)
            return 2

    else:
        print(f"✖ Path tidak ditemukan: {path_input}", file=sys.stderr)
        return 2


def _cetak_hasil_satu(hasil: Any) -> None:  # type: ignore[name-defined]
    """Cetak ringkasan hasil satu dokumen ke konsol."""
    from validator_dokumen.core.models import HasilValidasiDokumen

    simbol = {
        StatusValidasi.VALID: "✔ VALID",
        StatusValidasi.TIDAK_VALID: "✖ TIDAK VALID",
        StatusValidasi.PERLU_DICEK: "⚠ PERLU DICEK",
        StatusValidasi.TIDAK_BISA_DIBACA: "⦸ TIDAK BISA DIBACA",
    }.get(hasil.status, hasil.status.value)

    print(f"  Status  : {simbol}")
    if hasil.skema_terpakai:
        print(f"  Skema   : {hasil.skema_terpakai}")
    if hasil.skor_total:
        print(f"  Skor    : {hasil.skor}/{hasil.skor_total}")
    if hasil.baris_rekap_nomor:
        print(f"  Rekapan : {hasil.file_rekap}, baris {hasil.baris_rekap_nomor}")
    if hasil.error_teknis:
        print(f"  Error   : {hasil.error_teknis}")
    for masalah in hasil.masalah:
        print(f"  ⚠ {masalah}")


def cmd_profil_daftar(args: argparse.Namespace) -> int:
    """Tampilkan daftar profil yang tersedia."""
    ps = ProfileService()
    daftar = ps.daftar_profil()
    if not daftar:
        print("Tidak ada profil. Gunakan 'profil buat-contoh' untuk membuat profil contoh.")
        return 0

    print(f"{'ID':36}  {'Nama'}")
    print("-" * 70)
    for pid, nama, path in daftar:
        print(f"{pid}  {nama}")
        print(f"{'':36}  ({path})")
    return 0


def cmd_profil_buat_contoh(args: argparse.Namespace) -> int:
    """Buat profil contoh di folder profiles/."""
    ps = ProfileService()
    path = ps.buat_profil_contoh()
    print(f"✔ Profil contoh dibuat: {path}")
    return 0


def buat_parser() -> argparse.ArgumentParser:
    """Buat parser argumen CLI."""
    parser = argparse.ArgumentParser(
        prog="validator-dokumen",
        description="Validator Dokumen - Validasi PDF terhadap tabel rekapan.",
    )
    sub = parser.add_subparsers(dest="perintah", required=True)

    # Perintah validasi
    p_val = sub.add_parser("validasi", help="Validasi PDF (satu file atau folder)")
    p_val.add_argument("--profil", required=True, help="Path ke file profil .json")
    p_val.add_argument("--rekap", required=True, help="Path ke file rekapan Excel")
    p_val.add_argument("--input", required=True, help="Path ke file PDF atau folder PDF")
    p_val.add_argument("--sheet", default=None, help="Nama sheet Excel (default: sheet pertama)")
    p_val.add_argument("--header", type=int, default=1, help="Baris header Excel (default: 1)")
    p_val.add_argument("--subfolder", action="store_true", help="Sertakan subfolder")
    p_val.set_defaults(func=cmd_validasi)

    # Perintah profil
    p_profil = sub.add_parser("profil", help="Kelola profil validasi")
    sub_profil = p_profil.add_subparsers(dest="sub_perintah", required=True)

    p_daftar = sub_profil.add_parser("daftar", help="Tampilkan daftar profil")
    p_daftar.set_defaults(func=cmd_profil_daftar)

    p_contoh = sub_profil.add_parser("buat-contoh", help="Buat profil contoh")
    p_contoh.set_defaults(func=cmd_profil_buat_contoh)

    return parser


def main() -> None:
    """Entry point CLI."""
    parser = buat_parser()
    args = parser.parse_args()

    try:
        exit_code = args.func(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nDibatalkan oleh pengguna.")
        sys.exit(0)
    except Exception as e:
        log.exception("Error tidak terduga di CLI")
        print(f"\n✖ Error tidak terduga: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
