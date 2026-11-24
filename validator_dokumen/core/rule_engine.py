"""
core/rule_engine.py - Mesin aturan validasi tambahan.

Mendukung:
- Aturan per field: wajib ada, format pola, salah satu nilai, panjang, tanggal logika
- Kondisional JIKA-MAKA lewat editor visual
"""

from __future__ import annotations

import re
from typing import Any

from validator_dokumen.core.decision_trace import buat_langkah, jejak_aturan
from validator_dokumen.core.models import (
    AksiKondisional,
    AturanField,
    BarisRekap,
    HasilPasangan,
    KondisiJikaMaka,
    LangkahJejak,
    NilaiField,
    OperatorKondisi,
)
from validator_dokumen.core.normalizer import parse_angka, parse_tanggal

# ── Template pola teks siap pakai ─────────────────────────────────────────────
TEMPLATE_POLA: dict[str, str] = {
    "angka_saja": r"^\d+$",
    "huruf_angka": r"^[A-Za-z0-9]+$",
    "tanggal_dd_mm_yyyy": r"^\d{2}/\d{2}/\d{4}$",
    "nib": r"^\d{13}$",
    "npwp": r"^\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}$",
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "telepon_id": r"^(\+62|0)\d{8,12}$",
}


def evaluasi_aturan_field(
    aturan: AturanField,
    nilai_field: NilaiField | None,
    baris_rekap: BarisRekap | None = None,
) -> tuple[bool, str, LangkahJejak]:
    """
    Evaluasi satu aturan untuk satu field.

    Returns:
        (lolos: bool, pesan: str, jejak: LangkahJejak)
    """
    if not aturan.aktif:
        jejak = buat_langkah("aturan", f"Aturan '{aturan.tipe_aturan}' dinonaktifkan", hasil=None)
        return True, "", jejak

    nilai = nilai_field.nilai_mentah if nilai_field else ""

    if aturan.tipe_aturan == "wajib_ada":
        lolos = bool(nilai and nilai.strip())
        pesan = (
            aturan.pesan_kustom or f"Field '{aturan.field_nama}' wajib ada tapi tidak ditemukan."
        )
        jejak = jejak_aturan(
            "wajib_ada", nilai, lolos, "Nilai ditemukan" if lolos else "Nilai kosong"
        )
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "format_pola":
        pola_str = aturan.parameter.get("pola", "")
        # Cek apakah template
        if pola_str in TEMPLATE_POLA:
            pola_str = TEMPLATE_POLA[pola_str]
        try:
            lolos = bool(re.match(pola_str, nilai)) if nilai else False
        except re.error:
            lolos = False
        pesan = (
            aturan.pesan_kustom
            or f"Field '{aturan.field_nama}' tidak sesuai format yang diharapkan."
        )
        jejak = jejak_aturan("format_pola", nilai, lolos, f"Pola: {pola_str}")
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "salah_satu":
        pilihan = aturan.parameter.get("pilihan", [])
        # Jika pilihan dari kolom rekapan
        if baris_rekap and aturan.parameter.get("dari_kolom_rekap"):
            kolom = aturan.parameter["dari_kolom_rekap"]
            pilihan = [baris_rekap.data.get(kolom, "")]
        lolos = nilai in pilihan if pilihan else False
        pesan = aturan.pesan_kustom or (
            f"Field '{aturan.field_nama}' harus salah satu dari: {', '.join(str(p) for p in pilihan)}"
        )
        jejak = jejak_aturan("salah_satu", nilai, lolos, f"Pilihan: {pilihan}")
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "panjang":
        min_len = aturan.parameter.get("min", 0)
        max_len = aturan.parameter.get("max", None)
        panjang = len(nilai)
        if max_len is not None:
            lolos = min_len <= panjang <= max_len
            keterangan = f"Panjang: {panjang} (min {min_len}, maks {max_len})"
        else:
            lolos = panjang >= min_len
            keterangan = f"Panjang: {panjang} (min {min_len})"
        pesan = aturan.pesan_kustom or f"Field '{aturan.field_nama}' panjang tidak sesuai."
        jejak = jejak_aturan("panjang", nilai, lolos, keterangan)
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "mengandung":
        teks_wajib = aturan.parameter.get("teks", "")
        lolos = teks_wajib.lower() in nilai.lower() if teks_wajib else True
        pesan = (
            aturan.pesan_kustom or f"Field '{aturan.field_nama}' harus mengandung '{teks_wajib}'."
        )
        jejak = jejak_aturan("mengandung", nilai, lolos, f"Harus mengandung: {teks_wajib}")
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "tidak_mengandung":
        teks_dilarang = aturan.parameter.get("teks", "")
        lolos = teks_dilarang.lower() not in nilai.lower() if teks_dilarang else True
        pesan = (
            aturan.pesan_kustom
            or f"Field '{aturan.field_nama}' tidak boleh mengandung '{teks_dilarang}'."
        )
        jejak = jejak_aturan("tidak_mengandung", nilai, lolos, f"Dilarang: {teks_dilarang}")
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "tanggal_belum_kedaluwarsa":
        import datetime

        tgl = parse_tanggal(nilai)
        if tgl is None:
            lolos = False
            keterangan = "Gagal parse tanggal"
        else:
            tgl_obj = datetime.date(*tgl)
            lolos = tgl_obj >= datetime.date.today()
            keterangan = f"Tanggal: {tgl_obj}, hari ini: {datetime.date.today()}"
        pesan = aturan.pesan_kustom or f"Izin sudah kedaluwarsa: {nilai}"
        jejak = jejak_aturan("tanggal_belum_kedaluwarsa", nilai, lolos, keterangan)
        return lolos, "" if lolos else pesan, jejak

    elif aturan.tipe_aturan == "tanggal_terbit_lebih_kecil":
        # tanggal_terbit < tanggal_berakhir
        aturan.parameter.get("field_berakhir", "")
        # Implementasi lengkap butuh nilai field lain - placeholder untuk nilai
        lolos = True  # Akan dievaluasi dengan konteks
        jejak = buat_langkah(
            "aturan", "tanggal_terbit_lebih_kecil: perlu konteks multi-field", hasil=None
        )
        return lolos, "", jejak

    # Tipe aturan tidak dikenal
    jejak = buat_langkah("aturan", f"Tipe aturan tidak dikenal: {aturan.tipe_aturan}", hasil=None)
    return True, "", jejak


def evaluasi_semua_aturan_field(
    aturan_list: list[AturanField],
    hasil_field: tuple[NilaiField, ...],
    baris_rekap: BarisRekap | None = None,
) -> list[tuple[bool, str, LangkahJejak]]:
    """
    Evaluasi semua aturan field. Kembalikan daftar (lolos, pesan, jejak).
    """
    hasil: list[tuple[bool, str, LangkahJejak]] = []

    for aturan in aturan_list:
        if not aturan.aktif:
            continue

        # Cari nilai field yang sesuai
        nilai_field = None
        for nf in hasil_field:
            if nf.nama_field == aturan.field_nama:
                nilai_field = nf
                break

        lolos, pesan, jejak = evaluasi_aturan_field(aturan, nilai_field, baris_rekap)
        hasil.append((lolos, pesan, jejak))

    return hasil


# ══════════════════════════════════════════════════════════════════════════════
# EVALUASI KONDISIONAL JIKA-MAKA
# ══════════════════════════════════════════════════════════════════════════════


def _evaluasi_ekspresi(
    ekspresi: dict[str, Any],
    hasil_field: tuple[NilaiField, ...],
    baris_rekap: BarisRekap | None,
) -> bool:
    """Evaluasi satu ekspresi kondisi."""
    sumber = ekspresi.get("sumber", "field")  # "field" atau "rekap"
    nama = ekspresi.get("nama", "")
    operator_str = ekspresi.get("operator", "sama dengan")
    nilai_bandingan = ekspresi.get("nilai", "")

    # Dapatkan nilai aktual
    if sumber == "field":
        nilai_aktual = ""
        for nf in hasil_field:
            if nf.nama_field == nama:
                nilai_aktual = nf.nilai_mentah
                break
    else:
        nilai_aktual = baris_rekap.data.get(nama, "") if baris_rekap else ""

    try:
        operator = OperatorKondisi(operator_str)
    except ValueError:
        return False

    if operator == OperatorKondisi.SAMA_DENGAN:
        return nilai_aktual == nilai_bandingan

    elif operator == OperatorKondisi.TIDAK_SAMA:
        return nilai_aktual != nilai_bandingan

    elif operator == OperatorKondisi.BERISI:
        return nilai_bandingan.lower() in nilai_aktual.lower()

    elif operator == OperatorKondisi.LEBIH_BESAR:
        angka_a = parse_angka(nilai_aktual)
        angka_b = parse_angka(str(nilai_bandingan))
        if angka_a is not None and angka_b is not None:
            return bool(angka_a > angka_b)
        return False

    elif operator == OperatorKondisi.LEBIH_KECIL:
        angka_a = parse_angka(nilai_aktual)
        angka_b = parse_angka(str(nilai_bandingan))
        if angka_a is not None and angka_b is not None:
            return bool(angka_a < angka_b)
        return False

    elif operator == OperatorKondisi.KOSONG:
        return not bool(nilai_aktual and nilai_aktual.strip())

    elif operator == OperatorKondisi.TIDAK_KOSONG:
        return bool(nilai_aktual and nilai_aktual.strip())

    elif operator == OperatorKondisi.TERMASUK_DAFTAR:
        if isinstance(nilai_bandingan, list):
            daftar = nilai_bandingan
        else:
            daftar = [v.strip() for v in str(nilai_bandingan).split(",")]
        return nilai_aktual in daftar

    return False


def evaluasi_kondisi_jika_maka(
    kondisi_list: list[KondisiJikaMaka],
    hasil_field: tuple[NilaiField, ...],
    baris_rekap: BarisRekap | None,
    hasil_pasangan: list[HasilPasangan],
) -> list[tuple[bool, str, str, LangkahJejak]]:
    """
    Evaluasi semua kondisi JIKA-MAKA.

    Returns:
        Daftar (aksi_terpicu: bool, aksi: str, pesan: str, jejak)
    """
    hasil: list[tuple[bool, str, str, LangkahJejak]] = []

    for kondisi_jm in kondisi_list:
        if not kondisi_jm.aktif:
            continue

        # Evaluasi semua kondisi (AND/OR)
        kondisi_terpenuhi = _evaluasi_semua_kondisi(
            kondisi_jm.kondisi,
            hasil_field,
            baris_rekap,
        )

        if not kondisi_terpenuhi:
            hasil.append(
                (
                    False,
                    kondisi_jm.aksi.value,
                    "",
                    buat_langkah("kondisional", "Kondisi JIKA tidak terpenuhi", hasil=None),
                )
            )
            continue

        # Kondisi terpenuhi - evaluasi MAKA
        lolos, pesan = _evaluasi_aksi(
            kondisi_jm.aksi,
            kondisi_jm.parameter_aksi,
            hasil_field,
            baris_rekap,
            hasil_pasangan,
            kondisi_jm.pesan_kustom,
        )
        jejak = buat_langkah(
            "kondisional",
            f"Kondisi terpenuhi, aksi: {kondisi_jm.aksi.value}",
            hasil=lolos,
        )
        hasil.append((not lolos, kondisi_jm.aksi.value, pesan, jejak))

    return hasil


def _evaluasi_semua_kondisi(
    kondisi: tuple[dict[str, Any], ...],
    hasil_field: tuple[NilaiField, ...],
    baris_rekap: BarisRekap | None,
) -> bool:
    """Evaluasi tuple kondisi dengan logika AND/OR."""
    if not kondisi:
        return False

    hasil = _evaluasi_ekspresi(kondisi[0], hasil_field, baris_rekap)

    for ekspresi in kondisi[1:]:
        hubungan = ekspresi.get("hubungan", "AND")
        nilai_ekspresi = _evaluasi_ekspresi(ekspresi, hasil_field, baris_rekap)
        hasil = hasil and nilai_ekspresi if hubungan == "AND" else hasil or nilai_ekspresi

    return hasil


def _evaluasi_aksi(
    aksi: AksiKondisional,
    parameter: dict[str, Any],
    hasil_field: tuple[NilaiField, ...],
    baris_rekap: BarisRekap | None,
    hasil_pasangan: list[HasilPasangan],
    pesan_kustom: str,
) -> tuple[bool, str]:
    """
    Evaluasi aksi MAKA. Returns (lolos, pesan).
    lolos=True berarti tidak ada masalah.
    """
    if aksi == AksiKondisional.WAJIB_ADA_FIELD:
        field_nama = parameter.get("field_nama", "")
        ada = any(nf.nama_field == field_nama and nf.nilai_mentah.strip() for nf in hasil_field)
        pesan = pesan_kustom or f"Field '{field_nama}' wajib ada (aturan kondisional)."
        return ada, "" if ada else pesan

    elif aksi == AksiKondisional.KOLOM_REKAP_HARUS_BERNILAI:
        kolom = parameter.get("kolom", "")
        nilai_target = parameter.get("nilai", "")
        nilai_aktual = baris_rekap.data.get(kolom, "") if baris_rekap else ""
        lolos = nilai_aktual == nilai_target
        pesan = (
            pesan_kustom
            or f"Kolom rekapan '{kolom}' harus bernilai '{nilai_target}' (ada: '{nilai_aktual}')."
        )
        return lolos, "" if lolos else pesan

    elif aksi == AksiKondisional.FIELD_HARUS_COCOK_KOLOM:
        field_nama = parameter.get("field_nama", "")
        kolom_nama = parameter.get("kolom_nama", "")
        nilai_dok = ""
        for nf in hasil_field:
            if nf.nama_field == field_nama:
                nilai_dok = nf.nilai_mentah
                break
        nilai_rek = baris_rekap.data.get(kolom_nama, "") if baris_rekap else ""
        lolos = nilai_dok == nilai_rek
        pesan = pesan_kustom or (
            f"Field '{field_nama}' harus cocok dengan kolom '{kolom_nama}'. "
            f"Dokumen: '{nilai_dok}', Rekapan: '{nilai_rek}'."
        )
        return lolos, "" if lolos else pesan

    elif aksi == AksiKondisional.TANDAI_TIDAK_VALID:
        pesan = pesan_kustom or "Ditandai TIDAK VALID oleh aturan kondisional."
        return False, pesan

    return True, ""
