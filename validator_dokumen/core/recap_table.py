"""
core/recap_table.py - Pembaca dan pengindeks tabel rekapan.

Membaca Excel (semua sel sebagai TEXT) dan PDF tabel, membangun
indeks terbalik yang efisien untuk pencarian cepat pada puluhan ribu baris.
Semua nama kolom bersifat dinamis - tidak ada yang di-hardcode.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from validator_dokumen.core.models import BarisRekap, OpsiNormalisasi, TabelRekap
from validator_dokumen.core.normalizer import normalisasi_teks


def _hash_file(path: Path) -> str:
    """Hitung SHA-256 dari isi file untuk metadata reproduksi."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def baca_excel(
    path: Path,
    sheet_nama: str | None = None,
    baris_header: int = 1,
) -> TabelRekap:
    """
    Baca satu sheet Excel. Semua sel dibaca sebagai TEXT agar nol di depan
    tidak hilang. Kolom duplikat diberi akhiran _2, _3, dst.

    Args:
        path: Path ke file Excel (.xlsx/.xls).
        sheet_nama: Nama sheet, None = sheet pertama.
        baris_header: Nomor baris header (1-based).

    Returns:
        TabelRekap dengan semua baris dan metadata.

    Raises:
        FileNotFoundError: Jika file tidak ditemukan.
        ValueError: Jika sheet tidak ditemukan atau format tidak valid.
    """
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("openpyxl diperlukan untuk membaca Excel.") from e

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"Tidak bisa membuka Excel: {e}") from e

    # Pilih sheet
    if sheet_nama is None:
        ws = wb.active
        if ws is None:
            raise ValueError("Workbook tidak punya sheet aktif.")
    else:
        if sheet_nama not in wb.sheetnames:
            raise ValueError(
                f"Sheet '{sheet_nama}' tidak ditemukan. Sheet tersedia: {wb.sheetnames}"
            )
        ws = wb[sheet_nama]

    sheet_nama_aktif = ws.title

    # Baca semua baris sebagai daftar nilai string
    semua_baris: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        baris_str = [str(sel) if sel is not None and str(sel) != "None" else "" for sel in row]
        semua_baris.append(baris_str)

    wb.close()

    if not semua_baris:
        raise ValueError("Sheet kosong, tidak ada data.")

    # Ambil header dari baris_header (1-based)
    idx_header = baris_header - 1
    if idx_header >= len(semua_baris):
        raise ValueError(f"Baris header {baris_header} melebihi jumlah baris ({len(semua_baris)}).")

    header_mentah = semua_baris[idx_header]

    # Tangani nama kolom duplikat dan kosong
    kolom = _normalisasi_header(header_mentah)

    # Buat baris data (mulai setelah header)
    baris_data: list[BarisRekap] = []
    for nomor_relatif, row_data in enumerate(semua_baris[idx_header + 1 :], start=1):
        # Lewati baris yang semua selnya kosong
        if not any(sel.strip() for sel in row_data):
            continue

        # Sesuaikan panjang baris dengan kolom
        row_disesuaikan = row_data + [""] * max(0, len(kolom) - len(row_data))
        row_disesuaikan = row_disesuaikan[: len(kolom)]

        data_baris: dict[str, str] = dict(zip(kolom, row_disesuaikan, strict=False))

        baris_rekap = BarisRekap(
            id=str(uuid.uuid4()),
            data=data_baris,
            sumber_file=str(path),
            sumber_sheet=sheet_nama_aktif,
            nomor_baris_asli=idx_header + 1 + nomor_relatif,  # 1-based dari file asli
        )
        baris_data.append(baris_rekap)

    return TabelRekap(
        baris=tuple(baris_data),
        kolom=tuple(kolom),
        sumber_file=str(path),
        hash_file=_hash_file(path),
    )


def _normalisasi_header(header_mentah: list[str]) -> list[str]:
    """
    Normalisasi nama kolom: strip, ganti kosong dengan 'Kolom_N',
    ganti duplikat dengan akhiran _2, _3, dst.
    """
    kolom: list[str] = []
    hitungan: dict[str, int] = {}

    for i, nama in enumerate(header_mentah):
        nama_bersih = str(nama).strip() if nama else ""
        if not nama_bersih:
            nama_bersih = f"Kolom_{i + 1}"

        if nama_bersih in hitungan:
            hitungan[nama_bersih] += 1
            nama_bersih = f"{nama_bersih}_{hitungan[nama_bersih]}"
        else:
            hitungan[nama_bersih] = 1

        kolom.append(nama_bersih)

    return kolom


def gabung_tabel(tabel_list: list[TabelRekap]) -> TabelRekap:
    """
    Gabungkan beberapa TabelRekap menjadi satu.
    Kolom disesuaikan: kolom dari tabel pertama sebagai dasar.

    Args:
        tabel_list: Daftar tabel yang akan digabung.

    Returns:
        TabelRekap gabungan.

    Raises:
        ValueError: Jika daftar kosong.
    """
    if not tabel_list:
        raise ValueError("Tidak ada tabel untuk digabung.")

    if len(tabel_list) == 1:
        return tabel_list[0]

    # Gabungkan semua kolom (union, pertahankan urutan)
    semua_kolom: list[str] = list(tabel_list[0].kolom)
    for tabel in tabel_list[1:]:
        for kol in tabel.kolom:
            if kol not in semua_kolom:
                semua_kolom.append(kol)

    # Gabungkan semua baris
    semua_baris: list[BarisRekap] = []
    for tabel in tabel_list:
        for baris in tabel.baris:
            # Tambahkan kolom yang tidak ada dengan nilai kosong
            data_lengkap = dict(baris.data)
            for kol in semua_kolom:
                if kol not in data_lengkap:
                    data_lengkap[kol] = ""
            baris_baru = BarisRekap(
                id=baris.id,
                data=data_lengkap,
                sumber_file=baris.sumber_file,
                sumber_sheet=baris.sumber_sheet,
                nomor_baris_asli=baris.nomor_baris_asli,
            )
            semua_baris.append(baris_baru)

    # Hash gabungan dari semua file
    hash_gabungan = hashlib.sha256("|".join(t.hash_file for t in tabel_list).encode()).hexdigest()

    return TabelRekap(
        baris=tuple(semua_baris),
        kolom=tuple(semua_kolom),
        sumber_file="|".join(t.sumber_file for t in tabel_list),
        hash_file=hash_gabungan,
    )


# ══════════════════════════════════════════════════════════════════════════════
# INDEKS TERBALIK UNTUK PENCARIAN CEPAT
# ══════════════════════════════════════════════════════════════════════════════


class IndeksRekap:
    """
    Indeks terbalik untuk pencarian baris rekapan yang efisien.
    Dibangun sekali dari TabelRekap dan dipakai ulang untuk semua dokumen.

    Struktur: {nama_kolom: {nilai_ternormalisasi: set[id_baris]}}
    """

    def __init__(
        self,
        tabel: TabelRekap,
        kolom_diindeks: list[str],
        opsi_normalisasi: dict[str, OpsiNormalisasi],
    ) -> None:
        """
        Args:
            tabel: Tabel rekapan yang akan diindeks.
            kolom_diindeks: Daftar nama kolom yang perlu diindeks.
            opsi_normalisasi: {nama_kolom: OpsiNormalisasi} per kolom.
        """
        self._tabel = tabel
        self._kolom = kolom_diindeks
        self._opsi = opsi_normalisasi
        self._indeks: dict[str, dict[str, set[str]]] = {}
        self._id_ke_baris: dict[str, BarisRekap] = {b.id: b for b in tabel.baris}
        self._bangun_indeks()

    def _bangun_indeks(self) -> None:
        """Bangun indeks terbalik dari tabel rekapan."""
        for kolom in self._kolom:
            if kolom not in list(self._tabel.kolom):
                # Kolom tidak ada di tabel - catat tapi jangan crash
                self._indeks[kolom] = {}
                continue

            opsi = self._opsi.get(kolom, OpsiNormalisasi())
            indeks_kolom: dict[str, set[str]] = {}

            for baris in self._tabel.baris:
                nilai_mentah = baris.data.get(kolom, "")
                nilai_norm = normalisasi_teks(nilai_mentah, opsi)
                if nilai_norm:  # jangan indeks nilai kosong
                    if nilai_norm not in indeks_kolom:
                        indeks_kolom[nilai_norm] = set()
                    indeks_kolom[nilai_norm].add(baris.id)

            self._indeks[kolom] = indeks_kolom

    def cari_persis(self, kolom: str, nilai_norm: str) -> set[str]:
        """
        Cari baris berdasarkan nilai ternormalisasi persis.

        Returns:
            Set ID baris yang cocok.
        """
        return self._indeks.get(kolom, {}).get(nilai_norm, set())

    def cari_fuzzy(
        self,
        kolom: str,
        nilai_norm: str,
        ambang: float,
    ) -> list[tuple[str, float]]:
        """
        Cari baris dengan kemiripan fuzzy menggunakan rapidfuzz.

        Returns:
            Daftar (id_baris, skor) diurutkan skor tertinggi dulu.
        """
        try:
            from rapidfuzz import fuzz, process  # type: ignore[import-untyped]
        except ImportError:
            return []

        indeks_kolom = self._indeks.get(kolom, {})
        if not indeks_kolom:
            return []

        # Buat daftar pilihan: (nilai_norm_rekap, {id_baris_set})
        pilihan = list(indeks_kolom.keys())
        hasil_match = process.extract(
            nilai_norm,
            pilihan,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=ambang,
            limit=20,
        )

        baris_skor: list[tuple[str, float]] = []
        for nilai_rekap, skor, _ in hasil_match:
            for id_baris in indeks_kolom.get(nilai_rekap, set()):
                baris_skor.append((id_baris, float(skor)))

        # Urutkan skor tertinggi dulu (deterministik: sort stabil)
        baris_skor.sort(key=lambda x: (-x[1], x[0]))
        return baris_skor

    def cari_mengandung(self, kolom: str, nilai_norm: str) -> set[str]:
        """Cari baris yang nilai kolomnya mengandung nilai_norm."""
        hasil: set[str] = set()
        for nilai_rekap, id_set in self._indeks.get(kolom, {}).items():
            if nilai_norm in nilai_rekap:
                hasil.update(id_set)
        return hasil

    def cari_diawali(self, kolom: str, nilai_norm: str) -> set[str]:
        """Cari baris yang nilai kolomnya diawali dengan nilai_norm."""
        hasil: set[str] = set()
        for nilai_rekap, id_set in self._indeks.get(kolom, {}).items():
            if nilai_rekap.startswith(nilai_norm):
                hasil.update(id_set)
        return hasil

    def dapatkan_baris(self, id_baris: str) -> BarisRekap | None:
        """Dapatkan BarisRekap berdasarkan ID."""
        return self._id_ke_baris.get(id_baris)

    def semua_nilai_unik(self, kolom: str) -> list[str]:
        """Dapatkan semua nilai unik ternormalisasi untuk satu kolom."""
        return sorted(self._indeks.get(kolom, {}).keys())

    def statistik_kolom(self, kolom: str) -> dict[str, Any]:
        """
        Statistik kekuatan kunci untuk satu kolom.

        Returns:
            Dict berisi: total_baris, unik, kosong, duplikat
        """
        total = len(self._tabel.baris)
        indeks_kolom = self._indeks.get(kolom, {})
        unik = len(indeks_kolom)
        terisi = sum(len(ids) for ids in indeks_kolom.values())
        kosong = total - terisi
        duplikat = sum(len(ids) - 1 for ids in indeks_kolom.values() if len(ids) > 1)
        return {
            "total_baris": total,
            "unik": unik,
            "kosong": kosong,
            "duplikat": duplikat,
        }

    @property
    def tabel(self) -> TabelRekap:
        """Akses tabel rekapan."""
        return self._tabel
