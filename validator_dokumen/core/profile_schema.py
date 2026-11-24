"""
core/profile_schema.py - Serialisasi dan validasi profil JSON.

Semua konfigurasi disimpan sebagai JSON. Profil punya schema_version
dan fungsi migrasi. Validasi profil saat dimuat dengan pesan error
yang menunjuk bagian yang salah.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from validator_dokumen.core.constants import PROFILE_SCHEMA_VERSION
from validator_dokumen.core.models import (
    AksiKondisional,
    AturanField,
    DefinisiField,
    JikaAdaTidakCocok,
    KondisiJikaMaka,
    ModeCocok,
    OpsiNormalisasi,
    PasanganPencocokan,
    PeranPasangan,
    ProfilValidasi,
    SkemaPencocokan,
)

# ══════════════════════════════════════════════════════════════════════════════
# SERIALISASI (Profil -> Dict/JSON)
# ══════════════════════════════════════════════════════════════════════════════


def opsi_ke_dict(opsi: OpsiNormalisasi) -> dict[str, bool]:
    return {
        "abaikan_huruf_besar": opsi.abaikan_huruf_besar,
        "abaikan_spasi": opsi.abaikan_spasi,
        "abaikan_tanda_baca": opsi.abaikan_tanda_baca,
        "abaikan_awalan_badan_usaha": opsi.abaikan_awalan_badan_usaha,
        "abaikan_nol_depan": opsi.abaikan_nol_depan,
        "koreksi_ocr": opsi.koreksi_ocr,
        "hapus_karakter_tak_terlihat": opsi.hapus_karakter_tak_terlihat,
    }


def pasangan_ke_dict(pasangan: PasanganPencocokan) -> dict[str, Any]:
    return {
        "id": pasangan.id,
        "kolom_rekap": pasangan.kolom_rekap,
        "field_dokumen": pasangan.field_dokumen,
        "peran": pasangan.peran.value,
        "mode": pasangan.mode.value,
        "normalisasi": opsi_ke_dict(pasangan.normalisasi),
        "bobot": pasangan.bobot,
        "ambang_mirip": pasangan.ambang_mirip,
        "toleransi_numerik": pasangan.toleransi_numerik,
        "pesan_kesalahan_kustom": pasangan.pesan_kesalahan_kustom,
    }


def skema_ke_dict(skema: SkemaPencocokan) -> dict[str, Any]:
    return {
        "id": skema.id,
        "nama": skema.nama,
        "pasangan": [pasangan_ke_dict(p) for p in skema.pasangan],
        "k_minimum": skema.k_minimum,
        "aktif": skema.aktif,
        "gunakan_bobot": skema.gunakan_bobot,
        "jika_ada_tidak_cocok": skema.jika_ada_tidak_cocok.value,
        "min_selisih_skor": skema.min_selisih_skor,
    }


def field_ke_dict(field: DefinisiField) -> dict[str, Any]:
    return {
        "id": field.id,
        "nama": field.nama,
        "cara_ambil": field.cara_ambil,
        "parameter": field.parameter,
        "wajib": field.wajib,
        "deskripsi": field.deskripsi,
    }


def aturan_ke_dict(aturan: AturanField) -> dict[str, Any]:
    return {
        "id": aturan.id,
        "field_nama": aturan.field_nama,
        "tipe_aturan": aturan.tipe_aturan,
        "parameter": aturan.parameter,
        "aktif": aturan.aktif,
        "pesan_kustom": aturan.pesan_kustom,
    }


def kondisi_ke_dict(kondisi: KondisiJikaMaka) -> dict[str, Any]:
    return {
        "id": kondisi.id,
        "kondisi": list(kondisi.kondisi),
        "aksi": kondisi.aksi.value,
        "parameter_aksi": kondisi.parameter_aksi,
        "aktif": kondisi.aktif,
        "pesan_kustom": kondisi.pesan_kustom,
    }


def profil_ke_dict(profil: ProfilValidasi) -> dict[str, Any]:
    """Serialisasi ProfilValidasi ke dict siap JSON."""
    return {
        "schema_version": profil.schema_version,
        "id": profil.id,
        "nama": profil.nama,
        "deskripsi": profil.deskripsi,
        "field_dokumen": [field_ke_dict(f) for f in profil.field_dokumen],
        "skema_pencocokan": [skema_ke_dict(s) for s in profil.skema_pencocokan],
        "aturan_field": [aturan_ke_dict(a) for a in profil.aturan_field],
        "kondisi_jika_maka": [kondisi_ke_dict(k) for k in profil.kondisi_jika_maka],
        "pengaturan_ocr": profil.pengaturan_ocr,
        "dibuat_pada": profil.dibuat_pada,
        "diubah_pada": profil.diubah_pada,
    }


def simpan_profil(profil: ProfilValidasi, path: Path) -> None:
    """
    Simpan profil ke file JSON secara atomik (tulis ke .tmp lalu rename).

    Args:
        profil: Profil yang akan disimpan.
        path: Path file tujuan.

    Raises:
        OSError: Jika tidak bisa menulis file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path_tmp = path.with_suffix(".tmp")

    data = profil_ke_dict(profil)
    teks = json.dumps(data, ensure_ascii=False, indent=2)

    path_tmp.write_text(teks, encoding="utf-8")
    path_tmp.replace(path)


# ══════════════════════════════════════════════════════════════════════════════
# DESERIALISASI (Dict/JSON -> Profil)
# ══════════════════════════════════════════════════════════════════════════════


class ProfilTidakValid(Exception):
    """Profil JSON tidak valid atau tidak bisa dimigrasikan."""

    pass


def _dict_ke_opsi(d: dict[str, Any], konteks: str = "") -> OpsiNormalisasi:
    """Konversi dict ke OpsiNormalisasi dengan validasi."""
    try:
        return OpsiNormalisasi(
            abaikan_huruf_besar=bool(d.get("abaikan_huruf_besar", True)),
            abaikan_spasi=bool(d.get("abaikan_spasi", True)),
            abaikan_tanda_baca=bool(d.get("abaikan_tanda_baca", False)),
            abaikan_awalan_badan_usaha=bool(d.get("abaikan_awalan_badan_usaha", False)),
            abaikan_nol_depan=bool(d.get("abaikan_nol_depan", False)),
            koreksi_ocr=bool(d.get("koreksi_ocr", False)),
            hapus_karakter_tak_terlihat=bool(d.get("hapus_karakter_tak_terlihat", True)),
        )
    except Exception as e:
        raise ProfilTidakValid(f"[{konteks}] Opsi normalisasi tidak valid: {e}") from e


def _dict_ke_pasangan(d: dict[str, Any], konteks: str = "") -> PasanganPencocokan:
    """Konversi dict ke PasanganPencocokan dengan validasi."""
    try:
        peran_str = d.get("peran", "Poin")
        try:
            peran = PeranPasangan(peran_str)
        except ValueError:
            raise ProfilTidakValid(f"[{konteks}] Peran tidak valid: '{peran_str}'")

        mode_str = d.get("mode", "Persis setelah normalisasi")
        try:
            mode = ModeCocok(mode_str)
        except ValueError:
            raise ProfilTidakValid(f"[{konteks}] Mode cocok tidak valid: '{mode_str}'")

        return PasanganPencocokan(
            id=str(d.get("id", uuid.uuid4())),
            kolom_rekap=str(d.get("kolom_rekap", "")),
            field_dokumen=str(d.get("field_dokumen", "")),
            peran=peran,
            mode=mode,
            normalisasi=_dict_ke_opsi(d.get("normalisasi", {}), f"{konteks}.normalisasi"),
            bobot=float(d.get("bobot", 1.0)),
            ambang_mirip=float(d.get("ambang_mirip", 90.0)),
            toleransi_numerik=float(d.get("toleransi_numerik", 0.0)),
            pesan_kesalahan_kustom=str(d.get("pesan_kesalahan_kustom", "")),
        )
    except ProfilTidakValid:
        raise
    except Exception as e:
        raise ProfilTidakValid(f"[{konteks}] Pasangan tidak valid: {e}") from e


def _dict_ke_skema(d: dict[str, Any], indeks: int) -> SkemaPencocokan:
    """Konversi dict ke SkemaPencocokan dengan validasi."""
    konteks = f"skema[{indeks}]"
    try:
        pasangan_raw = d.get("pasangan", [])
        pasangan = tuple(
            _dict_ke_pasangan(p, f"{konteks}.pasangan[{i}]") for i, p in enumerate(pasangan_raw)
        )

        jika_str = d.get("jika_ada_tidak_cocok", JikaAdaTidakCocok.VALID_CATATAN.value)
        try:
            jika_ada = JikaAdaTidakCocok(jika_str)
        except ValueError:
            jika_ada = JikaAdaTidakCocok.VALID_CATATAN

        k = int(d.get("k_minimum", len(pasangan)))
        if k < 1:
            raise ProfilTidakValid(f"[{konteks}] k_minimum harus >= 1 (ada: {k}).")
        if k > len(pasangan) and pasangan:
            raise ProfilTidakValid(
                f"[{konteks}] k_minimum ({k}) melebihi jumlah pasangan ({len(pasangan)})."
            )

        return SkemaPencocokan(
            id=str(d.get("id", uuid.uuid4())),
            nama=str(d.get("nama", f"Skema {indeks + 1}")),
            pasangan=pasangan,
            k_minimum=k,
            aktif=bool(d.get("aktif", True)),
            gunakan_bobot=bool(d.get("gunakan_bobot", False)),
            jika_ada_tidak_cocok=jika_ada,
            min_selisih_skor=int(d.get("min_selisih_skor", 1)),
        )
    except ProfilTidakValid:
        raise
    except Exception as e:
        raise ProfilTidakValid(f"[{konteks}] Skema tidak valid: {e}") from e


def _dict_ke_field(d: dict[str, Any], indeks: int) -> DefinisiField:
    """Konversi dict ke DefinisiField dengan validasi."""
    konteks = f"field_dokumen[{indeks}]"
    cara = d.get("cara_ambil", "label")
    if cara not in ("label", "pola", "area", "kolom_tabel"):
        raise ProfilTidakValid(f"[{konteks}] cara_ambil tidak valid: '{cara}'")

    return DefinisiField(
        id=str(d.get("id", uuid.uuid4())),
        nama=str(d.get("nama", "")),
        cara_ambil=cara,
        parameter=dict(d.get("parameter", {})),
        wajib=bool(d.get("wajib", False)),
        deskripsi=str(d.get("deskripsi", "")),
    )


def _dict_ke_aturan(d: dict[str, Any], indeks: int) -> AturanField:
    """Konversi dict ke AturanField."""
    return AturanField(
        id=str(d.get("id", uuid.uuid4())),
        field_nama=str(d.get("field_nama", "")),
        tipe_aturan=str(d.get("tipe_aturan", "")),
        parameter=dict(d.get("parameter", {})),
        aktif=bool(d.get("aktif", True)),
        pesan_kustom=str(d.get("pesan_kustom", "")),
    )


def _dict_ke_kondisi(d: dict[str, Any], indeks: int) -> KondisiJikaMaka:
    """Konversi dict ke KondisiJikaMaka."""
    konteks = f"kondisi[{indeks}]"
    aksi_str = d.get("aksi", "")
    try:
        aksi = AksiKondisional(aksi_str)
    except ValueError:
        raise ProfilTidakValid(f"[{konteks}] Aksi kondisional tidak valid: '{aksi_str}'")

    return KondisiJikaMaka(
        id=str(d.get("id", uuid.uuid4())),
        kondisi=tuple(d.get("kondisi", [])),
        aksi=aksi,
        parameter_aksi=dict(d.get("parameter_aksi", {})),
        aktif=bool(d.get("aktif", True)),
        pesan_kustom=str(d.get("pesan_kustom", "")),
    )


def _migrasi_profil(data: dict[str, Any]) -> dict[str, Any]:
    """
    Migrasi profil dari versi lama ke versi saat ini.
    Tambahkan fungsi migrasi di sini saat schema_version naik.
    """
    data.get("schema_version", 1)

    # Contoh migrasi: versi 1 -> 2 (belum ada versi 2)
    # if versi == 1:
    #     data = migrasi_v1_ke_v2(data)
    #     versi = 2

    data["schema_version"] = PROFILE_SCHEMA_VERSION
    return data


def dict_ke_profil(data: dict[str, Any]) -> ProfilValidasi:
    """
    Deserialisasi dict ke ProfilValidasi dengan validasi lengkap.

    Raises:
        ProfilTidakValid: Jika profil tidak valid, dengan pesan yang menunjuk bagian yang salah.
    """
    if not isinstance(data, dict):
        raise ProfilTidakValid("Profil harus berupa objek JSON.")

    # Migrasi jika perlu
    data = _migrasi_profil(data)

    try:
        field_dokumen = tuple(
            _dict_ke_field(f, i) for i, f in enumerate(data.get("field_dokumen", []))
        )
        skema_pencocokan = tuple(
            _dict_ke_skema(s, i) for i, s in enumerate(data.get("skema_pencocokan", []))
        )
        aturan_field = tuple(
            _dict_ke_aturan(a, i) for i, a in enumerate(data.get("aturan_field", []))
        )
        kondisi_jika_maka = tuple(
            _dict_ke_kondisi(k, i) for i, k in enumerate(data.get("kondisi_jika_maka", []))
        )

        return ProfilValidasi(
            schema_version=int(data.get("schema_version", PROFILE_SCHEMA_VERSION)),
            id=str(data.get("id", uuid.uuid4())),
            nama=str(data.get("nama", "Profil Tanpa Nama")),
            deskripsi=str(data.get("deskripsi", "")),
            field_dokumen=field_dokumen,
            skema_pencocokan=skema_pencocokan,
            aturan_field=aturan_field,
            kondisi_jika_maka=kondisi_jika_maka,
            pengaturan_ocr=dict(data.get("pengaturan_ocr", {})),
            dibuat_pada=str(data.get("dibuat_pada", "")),
            diubah_pada=str(data.get("diubah_pada", "")),
        )
    except ProfilTidakValid:
        raise
    except Exception as e:
        raise ProfilTidakValid(f"Gagal mem-parse profil: {e}") from e


def muat_profil(path: Path) -> ProfilValidasi:
    """
    Muat profil dari file JSON.

    Args:
        path: Path ke file profil .json.

    Returns:
        ProfilValidasi yang sudah divalidasi.

    Raises:
        FileNotFoundError: Jika file tidak ditemukan.
        ProfilTidakValid: Jika JSON tidak valid atau struktur salah.
    """
    if not path.exists():
        raise FileNotFoundError(f"File profil tidak ditemukan: {path}")

    try:
        teks = path.read_text(encoding="utf-8")
        data = json.loads(teks)
    except json.JSONDecodeError as e:
        raise ProfilTidakValid(f"JSON tidak valid di '{path}': {e}") from e
    except OSError as e:
        raise ProfilTidakValid(f"Tidak bisa membaca file profil '{path}': {e}") from e

    return dict_ke_profil(data)


def hash_profil(profil: ProfilValidasi) -> str:
    """Hitung hash SHA-256 dari profil untuk metadata reproduksi."""
    data = profil_ke_dict(profil)
    teks = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(teks.encode()).hexdigest()


def profil_contoh() -> ProfilValidasi:
    """
    Buat profil contoh dengan 8 pasangan, K=6, dan 2 pasangan WAJIB.
    Semua nama kolom/field bersifat dinamis (dari data contoh).
    """
    opsi_std = OpsiNormalisasi(
        abaikan_huruf_besar=True,
        abaikan_spasi=True,
        abaikan_tanda_baca=False,
        abaikan_awalan_badan_usaha=True,
        abaikan_nol_depan=False,
        koreksi_ocr=False,
        hapus_karakter_tak_terlihat=True,
    )

    pasangan = [
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="No Izin",
            field_dokumen="nomor_izin",
            peran=PeranPasangan.WAJIB,
            mode=ModeCocok.PERSIS_NORMALISASI,
            normalisasi=opsi_std,
            pesan_kesalahan_kustom="Nomor izin tidak cocok dengan rekapan.",
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="NIB",
            field_dokumen="nib",
            peran=PeranPasangan.WAJIB,
            mode=ModeCocok.PERSIS_NORMALISASI,
            normalisasi=opsi_std,
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="Nama Perusahaan",
            field_dokumen="nama_perusahaan",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.MIRIP,
            normalisasi=opsi_std,
            ambang_mirip=85.0,
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="Jenis Usaha",
            field_dokumen="jenis_usaha",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.MENGANDUNG,
            normalisasi=opsi_std,
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="Alamat",
            field_dokumen="alamat",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.MIRIP,
            normalisasi=opsi_std,
            ambang_mirip=80.0,
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="Tanggal Terbit",
            field_dokumen="tanggal_terbit",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.TANGGAL_SAMA,
            normalisasi=opsi_std,
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="Tanggal Berakhir",
            field_dokumen="tanggal_berakhir",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.TANGGAL_DOKUMEN_LEBIH_BESAR,
            normalisasi=opsi_std,
        ),
        PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="NPWP",
            field_dokumen="npwp",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.PERSIS_NORMALISASI,
            normalisasi=OpsiNormalisasi(abaikan_nol_depan=True, abaikan_huruf_besar=True),
        ),
    ]

    skema = SkemaPencocokan(
        id=str(uuid.uuid4()),
        nama="Skema Utama (6 dari 8)",
        pasangan=tuple(pasangan),
        k_minimum=6,
        aktif=True,
        gunakan_bobot=False,
        jika_ada_tidak_cocok=JikaAdaTidakCocok.PERLU_DICEK,
        min_selisih_skor=1,
    )

    field_dokumen = [
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="nomor_izin",
            cara_ambil="label",
            parameter={"label": "Nomor Izin", "sinonim": ["No. Izin", "No Izin", "Nomor"]},
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="nib",
            cara_ambil="pola",
            parameter={"pola": r"NIB[:\s]+(\d{13})"},
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="nama_perusahaan",
            cara_ambil="label",
            parameter={"label": "Nama Perusahaan", "sinonim": ["Nama Usaha", "Nama Perusahaan:"]},
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="jenis_usaha",
            cara_ambil="label",
            parameter={"label": "Jenis Usaha", "sinonim": ["Bidang Usaha", "Kegiatan"]},
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="alamat",
            cara_ambil="label",
            parameter={"label": "Alamat", "sinonim": ["Lokasi", "Tempat Usaha"]},
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="tanggal_terbit",
            cara_ambil="pola",
            parameter={
                "pola": r"(?:diterbitkan|terbit|tanggal)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})"
            },
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="tanggal_berakhir",
            cara_ambil="pola",
            parameter={
                "pola": r"(?:berlaku\s+hingga|berakhir|masa\s+berlaku)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})"
            },
        ),
        DefinisiField(
            id=str(uuid.uuid4()),
            nama="npwp",
            cara_ambil="pola",
            parameter={"pola": r"NPWP[:\s]+(\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})"},
        ),
    ]

    sekarang = datetime.now(UTC).isoformat()
    return ProfilValidasi(
        schema_version=PROFILE_SCHEMA_VERSION,
        id=str(uuid.uuid4()),
        nama="Profil Contoh - Izin Usaha (6 dari 8)",
        deskripsi="Profil contoh untuk validasi izin usaha. 2 pasangan WAJIB (No Izin, NIB), 6 dari 8 total.",
        field_dokumen=tuple(field_dokumen),
        skema_pencocokan=(skema,),
        aturan_field=(),
        kondisi_jika_maka=(),
        pengaturan_ocr={"lang": "ind+eng", "dpi": 300, "confidence_min": 80},
        dibuat_pada=sekarang,
        diubah_pada=sekarang,
    )
