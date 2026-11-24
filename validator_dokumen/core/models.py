"""
core/models.py - Model data utama aplikasi Validator Dokumen.

Semua model menggunakan dataclass(frozen=True, slots=True) atau Pydantic.
Status memakai Enum, bukan string bebas.
Tidak ada nama kolom/field yang di-hardcode di sini.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ══════════════════════════════════════════════════════════════════════════════
# ENUM STATUS VALIDASI
# ══════════════════════════════════════════════════════════════════════════════


class StatusValidasi(Enum):
    """Status hasil validasi satu dokumen."""

    VALID = "VALID"
    TIDAK_VALID = "TIDAK_VALID"
    PERLU_DICEK = "PERLU_DICEK"
    TIDAK_BISA_DIBACA = "TIDAK_BISA_DIBACA"


class PeranPasangan(Enum):
    """Peran sebuah pasangan dalam skema pencocokan."""

    WAJIB = "Wajib"  # harus cocok, berapa pun skor total
    POIN = "Poin"  # dihitung dalam skor K dari N
    KUNCI = "Wajib"  # alias Kunci (harus cocok untuk pencarian baris)
    PEMBANDING = "Poin"  # alias Pembanding (dihitung dalam K dari N)


class ModeCocok(Enum):
    """Cara membandingkan nilai dokumen dengan nilai rekapan."""

    PERSIS = "Persis"
    PERSIS_NORMALISASI = "Persis setelah normalisasi"
    MIRIP = "Mirip"
    MENGANDUNG = "Mengandung"
    DIAWALI = "Diawali dengan"
    NUMERIK = "Numerik"
    TANGGAL_SAMA = "Tanggal sama persis"
    TANGGAL_DOKUMEN_LEBIH_KECIL = "Tanggal dokumen <= rekapan"
    TANGGAL_DOKUMEN_LEBIH_BESAR = "Tanggal dokumen >= rekapan"


class SumberData(Enum):
    """Asal data yang diekstrak dari dokumen PDF."""

    TEKS = "TEKS"
    OCR = "OCR"


class AksiKondisional(Enum):
    """Aksi yang dijalankan jika kondisi JIKA-MAKA terpenuhi."""

    WAJIB_ADA_FIELD = "wajib_ada_field"
    KOLOM_REKAP_HARUS_BERNILAI = "kolom_rekap_harus_bernilai"
    FIELD_HARUS_COCOK_KOLOM = "field_harus_cocok_kolom"
    TANDAI_TIDAK_VALID = "tandai_tidak_valid"


class OperatorKondisi(Enum):
    """Operator perbandingan untuk kondisi JIKA-MAKA."""

    SAMA_DENGAN = "sama dengan"
    TIDAK_SAMA = "tidak sama"
    BERISI = "berisi"
    LEBIH_BESAR = ">"
    LEBIH_KECIL = "<"
    KOSONG = "kosong"
    TIDAK_KOSONG = "tidak kosong"
    TERMASUK_DAFTAR = "termasuk daftar"


class JikaAdaTidakCocok(Enum):
    """Perlakuan saat ada pasangan tidak cocok walau K terpenuhi."""

    VALID_CATATAN = "valid_catatan"
    PERLU_DICEK = "perlu_dicek"
    TIDAK_VALID = "tidak_valid"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL DATA (frozen dataclass)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class OpsiNormalisasi:
    """Opsi normalisasi yang bisa dinyalakan per pasangan."""

    abaikan_huruf_besar: bool = True
    abaikan_spasi: bool = True
    abaikan_tanda_baca: bool = False
    abaikan_awalan_badan_usaha: bool = False
    abaikan_nol_depan: bool = False
    koreksi_ocr: bool = False
    hapus_karakter_tak_terlihat: bool = True


@dataclass(frozen=True, slots=True)
class PasanganPencocokan:
    """
    Satu baris dalam skema pencocokan:
    kolom rekapan <-> field dokumen, dengan cara cocok dan opsi.
    """

    id: str  # ID unik pasangan (uuid)
    kolom_rekap: str  # nama kolom di rekapan (dinamis)
    field_dokumen: str  # nama field di dokumen (dinamis)
    peran: PeranPasangan
    mode: ModeCocok
    normalisasi: OpsiNormalisasi
    bobot: float = 1.0  # dipakai jika bobot diaktifkan di skema
    ambang_mirip: float = 90.0  # hanya relevan jika mode == MIRIP
    toleransi_numerik: float = 0.0  # hanya relevan jika mode == NUMERIK
    pesan_kesalahan_kustom: str = ""  # pesan kustom; kosong = pesan default


@dataclass(frozen=True, slots=True)
class SkemaPencocokan:
    """
    Satu skema pencocokan: N pasangan, parameter K, dan perlakuan.
    Satu profil bisa punya banyak skema berurutan prioritas.
    """

    id: str
    nama: str
    pasangan: tuple[PasanganPencocokan, ...]
    k_minimum: int  # minimal pasangan yang harus cocok
    aktif: bool = True
    gunakan_bobot: bool = False  # jika True, K adalah skor bobot minimum
    jika_ada_tidak_cocok: JikaAdaTidakCocok = JikaAdaTidakCocok.VALID_CATATAN
    min_selisih_skor: int = 1  # selisih skor min antara peringkat 1 dan 2


@dataclass(frozen=True, slots=True)
class DefinisiField:
    """
    Definisi cara mengambil satu field dari dokumen PDF.
    Pengguna mendefinisikan ini lewat UI; tidak ada nama field bawaan.
    """

    id: str
    nama: str  # nama field yang ditampilkan & dipakai di peta
    cara_ambil: str  # "label" | "pola" | "area" | "kolom_tabel"
    parameter: dict[str, Any]  # parameter spesifik cara ambil (fleksibel)
    wajib: bool = False  # jika True dan tidak ditemukan -> TIDAK VALID
    deskripsi: str = ""


@dataclass(frozen=True, slots=True)
class AturanField:
    """Aturan validasi tambahan untuk satu field dokumen."""

    id: str
    field_nama: str
    tipe_aturan: str  # "format_pola" | "salah_satu" | "panjang" | "tanggal_logika" | dll.
    parameter: dict[str, Any]
    aktif: bool = True
    pesan_kustom: str = ""


@dataclass(frozen=True, slots=True)
class KondisiJikaMaka:
    """Satu kondisi JIKA-MAKA dalam aturan kondisional."""

    id: str
    # Daftar ekspresi kondisi yang di-AND/OR
    kondisi: tuple[dict[str, Any], ...]  # [{sumber, kolom/field, operator, nilai, hubungan}]
    aksi: AksiKondisional
    parameter_aksi: dict[str, Any]
    aktif: bool = True
    pesan_kustom: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# PROFIL
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ProfilValidasi:
    """
    Profil lengkap: semua konfigurasi yang disimpan sebagai JSON.
    schema_version dipakai untuk migrasi.
    """

    schema_version: int
    id: str
    nama: str
    deskripsi: str
    field_dokumen: tuple[DefinisiField, ...]
    skema_pencocokan: tuple[SkemaPencocokan, ...]
    aturan_field: tuple[AturanField, ...]
    kondisi_jika_maka: tuple[KondisiJikaMaka, ...]
    pengaturan_ocr: dict[str, Any] = field(default_factory=dict)
    dibuat_pada: str = ""
    diubah_pada: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# HASIL EKSTRAKSI & VALIDASI
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class NilaiField:
    """Hasil ekstraksi satu field dari satu dokumen PDF."""

    nama_field: str
    nilai_mentah: str
    nilai_normalisasi: str
    halaman: int
    kotak: tuple[float, float, float, float] | None  # (x0, y0, x1, y1)
    sumber: SumberData
    confidence: float  # 100.0 untuk TEKS
    kandidat_lain: tuple[str, ...]  # jika ada >1 kandidat
    meragukan: bool = False  # True jika confidence rendah


@dataclass(frozen=True, slots=True)
class LangkahJejak:
    """Satu langkah dalam jejak keputusan (decision trace)."""

    langkah: str  # "normalisasi" | "pencocokan" | "aturan" | dll.
    keterangan: str
    nilai_masuk: str = ""
    nilai_keluar: str = ""
    hasil: bool | None = None  # True=cocok, False=tidak, None=info


@dataclass(frozen=True, slots=True)
class HasilPasangan:
    """Hasil pencocokan satu pasangan dalam satu skema."""

    pasangan_id: str
    kolom_rekap: str
    field_dokumen: str
    nilai_dokumen: str
    nilai_rekap: str
    cocok: bool
    skor_mirip: float | None  # skor rapidfuzz jika mode MIRIP
    meragukan: bool  # dari OCR confidence rendah
    jejak: tuple[LangkahJejak, ...]
    pesan_kesalahan: str = ""


@dataclass(frozen=True, slots=True)
class HasilSkema:
    """Hasil penerapan satu skema terhadap satu dokumen."""

    skema_id: str
    skema_nama: str
    baris_rekap_id: str | None  # ID baris rekapan yang ditemukan
    baris_rekap_nomor: int | None  # nomor baris di file asli
    file_rekap: str = ""
    sheet_rekap: str = ""
    skor: int = 0  # jumlah pasangan yang cocok
    skor_total: int = 0  # total pasangan N
    pasangan_hasil: tuple[HasilPasangan, ...] = ()
    kandidat_lain: tuple[tuple[str, int], ...] = ()  # (baris_id, skor)
    status: StatusValidasi = StatusValidasi.TIDAK_VALID
    alasan: str = ""


@dataclass(frozen=True, slots=True)
class HasilValidasiDokumen:
    """
    Hasil validasi lengkap satu dokumen PDF.
    Membawa jejak keputusan lengkap untuk reproduksi dan audit.
    """

    nama_file: str
    path_file: str
    status: StatusValidasi
    skema_terpakai: str | None  # nama skema yang berhasil/dipakai
    skor: int = 0
    skor_total: int = 0
    baris_rekap_nomor: int | None = None
    file_rekap: str = ""
    sheet_rekap: str = ""
    hasil_field: tuple[NilaiField, ...] = ()
    hasil_skema: tuple[HasilSkema, ...] = ()  # semua skema yang dicoba
    masalah: tuple[str, ...] = ()
    jejak_keputusan: tuple[LangkahJejak, ...] = ()
    waktu_proses_detik: float = 0.0
    error_teknis: str = ""  # pesan error jika TIDAK_BISA_DIBACA


@dataclass(frozen=True, slots=True)
class BarisRekap:
    """Satu baris data rekapan dengan metadata sumber."""

    id: str  # ID unik internal (uuid)
    data: dict[str, str]  # kolom -> nilai (SEMUA STRING)
    sumber_file: str  # path file Excel/PDF rekapan
    sumber_sheet: str  # nama sheet (atau "" jika bukan Excel)
    nomor_baris_asli: int  # nomor baris di file sumber (1-based, termasuk header)


@dataclass(frozen=True, slots=True)
class TabelRekap:
    """Tabel rekapan lengkap: semua baris + kolom + metadata."""

    baris: tuple[BarisRekap, ...]
    kolom: tuple[str, ...]  # urutan kolom
    sumber_file: str
    hash_file: str  # SHA-256 untuk reproduksi


@dataclass(frozen=True, slots=True)
class HasilBulk:
    """Hasil validasi bulk: semua dokumen + statistik."""

    hasil_per_file: tuple[HasilValidasiDokumen, ...]
    folder_output: str
    total: int
    valid: int
    tidak_valid: int
    perlu_dicek: int
    tidak_bisa_dibaca: int
    waktu_mulai: str
    waktu_selesai: str
    versi_app: str
    nama_profil: str
    hash_profil: str
    hash_rekap: str
