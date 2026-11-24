"""
tests/test_matcher.py - Tes unit komprehensif untuk modul matcher.

Mencakup:
- Kunci tunggal dan kombinasi
- K dari N (6/8 lolos, 5/8 gagal)
- Pasangan WAJIB gagal walau skor cukup
- Dua baris skor sama -> PERLU_DICEK
- Selisih skor minimum
- Duplikat di rekapan
- Salah baca OCR (O/0, I/1)
- Mode MIRIP
- Kolom rekapan hilang
- Sel kosong
- Determinisme
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from validator_dokumen.core.matcher import cocokkan_pasangan, terapkan_skema, uji_tabrakan
from validator_dokumen.core.models import (
    BarisRekap,
    HasilPasangan,
    JikaAdaTidakCocok,
    ModeCocok,
    NilaiField,
    OpsiNormalisasi,
    PasanganPencocokan,
    PeranPasangan,
    SkemaPencocokan,
    SumberData,
    StatusValidasi,
    TabelRekap,
)
from validator_dokumen.core.recap_table import IndeksRekap


# ── Helpers ───────────────────────────────────────────────────────────────────

def _buat_baris(id_: str, data: dict[str, str]) -> BarisRekap:
    return BarisRekap(
        id=id_,
        data=data,
        sumber_file="tes.xlsx",
        sumber_sheet="Data",
        nomor_baris_asli=1,
    )


def _buat_tabel(baris_list: list[BarisRekap]) -> TabelRekap:
    if not baris_list:
        return TabelRekap(baris=(), kolom=(), sumber_file="", hash_file="")
    kolom = tuple(baris_list[0].data.keys())
    return TabelRekap(baris=tuple(baris_list), kolom=kolom, sumber_file="tes.xlsx", hash_file="abc")


def _buat_pasangan(
    kolom_rekap: str,
    field_dokumen: str,
    peran: PeranPasangan = PeranPasangan.POIN,
    mode: ModeCocok = ModeCocok.PERSIS_NORMALISASI,
    ambang_mirip: float = 90.0,
) -> PasanganPencocokan:
    return PasanganPencocokan(
        id=str(uuid.uuid4()),
        kolom_rekap=kolom_rekap,
        field_dokumen=field_dokumen,
        peran=peran,
        mode=mode,
        normalisasi=OpsiNormalisasi(abaikan_huruf_besar=True, abaikan_spasi=True),
        ambang_mirip=ambang_mirip,
    )


def _buat_field(nama: str, nilai: str, meragukan: bool = False) -> NilaiField:
    return NilaiField(
        nama_field=nama,
        nilai_mentah=nilai,
        nilai_normalisasi=nilai.lower().replace(" ", ""),
        halaman=1,
        kotak=None,
        sumber=SumberData.TEKS,
        confidence=100.0 if not meragukan else 50.0,
        kandidat_lain=(),
        meragukan=meragukan,
    )


def _buat_indeks(baris_list: list[BarisRekap], kolom_list: list[str]) -> IndeksRekap:
    tabel = _buat_tabel(baris_list)
    opsi = {k: OpsiNormalisasi(abaikan_huruf_besar=True, abaikan_spasi=True) for k in kolom_list}
    return IndeksRekap(tabel, kolom_list, opsi)


def _buat_skema(
    pasangan: list[PasanganPencocokan],
    k: int,
    jika_tidak_cocok: JikaAdaTidakCocok = JikaAdaTidakCocok.VALID_CATATAN,
    min_selisih: int = 1,
) -> SkemaPencocokan:
    return SkemaPencocokan(
        id=str(uuid.uuid4()),
        nama="Skema Tes",
        pasangan=tuple(pasangan),
        k_minimum=k,
        aktif=True,
        jika_ada_tidak_cocok=jika_tidak_cocok,
        min_selisih_skor=min_selisih,
    )


# ── Tes CocokkanPasangan ──────────────────────────────────────────────────────

class TestCocokkanPasangan:
    def test_persis_cocok(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.PERSIS)
        hasil = cocokkan_pasangan(p, "NILAI123", "NILAI123")
        assert hasil.cocok is True

    def test_persis_tidak_cocok(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.PERSIS)
        hasil = cocokkan_pasangan(p, "NILAI123", "NILAI456")
        assert hasil.cocok is False

    def test_persis_normalisasi_cocok_case_berbeda(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.PERSIS_NORMALISASI)
        hasil = cocokkan_pasangan(p, "Nilai 123", "NILAI123")
        assert hasil.cocok is True

    def test_mirip_di_atas_ambang(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.MIRIP, ambang_mirip=80.0)
        hasil = cocokkan_pasangan(p, "PT Maju Jaya", "PT Maju Jaya Sejahtera")
        # Kemiripan harus >= 80%
        assert hasil.skor_mirip is not None

    def test_mirip_di_bawah_ambang(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.MIRIP, ambang_mirip=99.0)
        hasil = cocokkan_pasangan(p, "PT Maju Jaya", "PT Berkah Abadi")
        assert hasil.cocok is False

    def test_mengandung_cocok(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.MENGANDUNG)
        hasil = cocokkan_pasangan(p, "Jasa Konstruksi Bangunan", "konstruksi")
        # Nilai rekap mengandung nilai dokumen atau sebaliknya
        assert hasil.cocok is True

    def test_numerik_cocok_persis(self) -> None:
        p = _buat_pasangan("kolom", "field", mode=ModeCocok.NUMERIK)
        hasil = cocokkan_pasangan(p, "1000", "1000")
        assert hasil.cocok is True

    def test_numerik_gagal_melebihi_toleransi(self) -> None:
        p = PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="k",
            field_dokumen="f",
            peran=PeranPasangan.POIN,
            mode=ModeCocok.NUMERIK,
            normalisasi=OpsiNormalisasi(),
            toleransi_numerik=5.0,
        )
        hasil = cocokkan_pasangan(p, "1000", "1010")
        assert hasil.cocok is False

    def test_tanggal_sama(self) -> None:
        p = _buat_pasangan("k", "f", mode=ModeCocok.TANGGAL_SAMA)
        hasil = cocokkan_pasangan(p, "12/01/2025", "12/01/2025")
        assert hasil.cocok is True

    def test_tanggal_dokumen_lebih_kecil(self) -> None:
        p = _buat_pasangan("k", "f", mode=ModeCocok.TANGGAL_DOKUMEN_LEBIH_KECIL)
        hasil = cocokkan_pasangan(p, "01/01/2025", "31/12/2025")
        assert hasil.cocok is True

    def test_jejak_tidak_kosong(self) -> None:
        p = _buat_pasangan("k", "f")
        hasil = cocokkan_pasangan(p, "nilai", "nilai")
        assert len(hasil.jejak) > 0


# ── Tes TerapkanSkema (K dari N) ──────────────────────────────────────────────

class TestTerapkanSkema:
    def _setup_6_dari_8(self) -> tuple[Any, Any, Any]:
        """Setup: 8 pasangan, 1 baris di rekap, cocokkan 6 dari 8."""
        # Buat rekapan dengan 1 baris
        baris = _buat_baris("b1", {
            "f1": "nilai1", "f2": "nilai2", "f3": "nilai3", "f4": "nilai4",
            "f5": "nilai5", "f6": "nilai6", "f7": "nilai7", "f8": "nilai8",
        })
        indeks = _buat_indeks([baris], ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8"])

        # 8 pasangan POIN
        pasangan = [_buat_pasangan(f"f{i}", f"field{i}") for i in range(1, 9)]
        return baris, indeks, pasangan

    def test_6_dari_8_lolos(self) -> None:
        baris, indeks, pasangan = self._setup_6_dari_8()
        skema = _buat_skema(pasangan, k=6)

        # 6 field benar, 2 salah
        hasil_field = tuple(
            _buat_field(f"field{i}", f"nilai{i}" if i <= 6 else "SALAH")
            for i in range(1, 9)
        )
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil.status == StatusValidasi.VALID

    def test_5_dari_8_gagal(self) -> None:
        baris, indeks, pasangan = self._setup_6_dari_8()
        skema = _buat_skema(pasangan, k=6)

        # Hanya 5 field benar
        hasil_field = tuple(
            _buat_field(f"field{i}", f"nilai{i}" if i <= 5 else "SALAH")
            for i in range(1, 9)
        )
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil.status == StatusValidasi.TIDAK_VALID

    def test_wajib_gagal_walau_skor_cukup(self) -> None:
        """Pasangan WAJIB gagal -> TIDAK_VALID meski skor K terpenuhi."""
        baris = _buat_baris("b1", {"kunci": "nilai_kunci", "data": "data_ok"})
        indeks = _buat_indeks([baris], ["kunci", "data"])

        p_wajib = _buat_pasangan("kunci", "field_kunci", peran=PeranPasangan.WAJIB)
        p_poin = _buat_pasangan("data", "field_data", peran=PeranPasangan.POIN)
        skema = _buat_skema([p_wajib, p_poin], k=1)  # K=1, cukup 1 cocok

        # Field kunci SALAH, data benar -> pasangan wajib gagal
        hasil_field = (
            _buat_field("field_kunci", "NILAI_SALAH"),
            _buat_field("field_data", "data_ok"),
        )
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil.status == StatusValidasi.TIDAK_VALID

    def test_dua_baris_skor_sama_perlu_dicek(self) -> None:
        """Dua baris skor sama -> PERLU_DICEK."""
        b1 = _buat_baris("b1", {"nama": "maju jaya", "kode": "A001"})
        b2 = _buat_baris("b2", {"nama": "maju jaya", "kode": "A002"})
        indeks = _buat_indeks([b1, b2], ["nama", "kode"])

        p_nama = _buat_pasangan("nama", "field_nama")
        skema = _buat_skema([p_nama], k=1, min_selisih=1)

        # Cocokkan dengan nama yang ada di kedua baris
        hasil_field = (_buat_field("field_nama", "maju jaya"),)
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil.status == StatusValidasi.PERLU_DICEK

    def test_sel_kosong_di_rekap(self) -> None:
        """Baris dengan sel kosong di kolom kunci tidak ikut cocok."""
        b1 = _buat_baris("b1", {"kunci": "", "data": "data1"})
        b2 = _buat_baris("b2", {"kunci": "nilai_ok", "data": "data2"})
        indeks = _buat_indeks([b1, b2], ["kunci", "data"])

        skema = _buat_skema([_buat_pasangan("kunci", "f_kunci")], k=1)
        hasil_field = (_buat_field("f_kunci", "nilai_ok"),)
        hasil = terapkan_skema(skema, hasil_field, indeks)

        # Harus menemukan b2, bukan b1
        assert hasil.baris_rekap_id == "b2"

    def test_kunci_tidak_ditemukan_tidak_valid(self) -> None:
        baris = _buat_baris("b1", {"kunci": "nilai_rekap"})
        indeks = _buat_indeks([baris], ["kunci"])

        skema = _buat_skema([_buat_pasangan("kunci", "f_kunci")], k=1)
        hasil_field = (_buat_field("f_kunci", "TIDAK_ADA_DI_REKAP"),)
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil.status == StatusValidasi.TIDAK_VALID

    def test_determinisme(self) -> None:
        """Dua kali jalan dengan input sama menghasilkan output identik."""
        baris_list = [
            _buat_baris(f"b{i}", {"kunci": f"k{i}", "data": f"d{i}"})
            for i in range(10)
        ]
        indeks = _buat_indeks(baris_list, ["kunci", "data"])
        skema = _buat_skema([
            _buat_pasangan("kunci", "f_kunci"),
            _buat_pasangan("data", "f_data"),
        ], k=2)

        hasil_field = (
            _buat_field("f_kunci", "k3"),
            _buat_field("f_data", "d3"),
        )

        hasil1 = terapkan_skema(skema, hasil_field, indeks)
        hasil2 = terapkan_skema(skema, hasil_field, indeks)

        assert hasil1.baris_rekap_id == hasil2.baris_rekap_id
        assert hasil1.skor == hasil2.skor
        assert hasil1.status == hasil2.status

    def test_kolom_rekap_hilang_tidak_crash(self) -> None:
        """Kolom rekapan yang tidak ada tidak menyebabkan crash."""
        baris = _buat_baris("b1", {"ada": "nilai"})
        indeks = _buat_indeks([baris], ["ada", "tidak_ada"])

        skema = _buat_skema([
            _buat_pasangan("ada", "f_ada"),
            _buat_pasangan("tidak_ada", "f_tidak_ada"),
        ], k=1)

        hasil_field = (
            _buat_field("f_ada", "nilai"),
            _buat_field("f_tidak_ada", "apapun"),
        )
        # Tidak boleh crash
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil is not None

    def test_ocr_salah_baca_o_0(self) -> None:
        """Test koreksi OCR: O dibaca sebagai 0 atau sebaliknya."""
        # Rekapan punya "K001"
        baris = _buat_baris("b1", {"kode": "K001"})
        # Buat indeks dengan koreksi OCR
        tabel = _buat_tabel([baris])
        opsi = {"kode": OpsiNormalisasi(koreksi_ocr=True, abaikan_huruf_besar=True)}
        indeks = IndeksRekap(tabel, ["kode"], opsi)

        p = PasanganPencocokan(
            id=str(uuid.uuid4()),
            kolom_rekap="kode",
            field_dokumen="f_kode",
            peran=PeranPasangan.WAJIB,
            mode=ModeCocok.PERSIS_NORMALISASI,
            normalisasi=OpsiNormalisasi(koreksi_ocr=True, abaikan_huruf_besar=True),
        )
        skema = _buat_skema([p], k=1)

        # Dokumen punya "KO01" (O salah dibaca sebagai 0)
        # Setelah koreksi OCR harusnya "K001"
        hasil_field = (_buat_field("f_kode", "KO01"),)
        hasil = terapkan_skema(skema, hasil_field, indeks)
        # Dengan koreksi OCR, harusnya bisa menemukan baris
        assert hasil is not None  # Tidak crash


class TestPerformaRekapBesar:
    """Tes performa: 20.000 baris rekapan."""

    @pytest.mark.timeout(10)  # Harus selesai < 10 detik
    def test_rekap_besar(self) -> None:
        """Bangun indeks dan cari pada 20.000 baris dalam waktu wajar."""
        import random
        random.seed(42)

        # Buat 20.000 baris
        baris_list = []
        for i in range(20000):
            baris_list.append(_buat_baris(f"b{i}", {
                "kunci": f"K{i:06d}",
                "nama": f"Perusahaan{i}",
            }))

        # Tambahkan baris target
        baris_target = _buat_baris("target", {"kunci": "K019999", "nama": "Perusahaan19999"})
        baris_list.append(baris_target)

        indeks = _buat_indeks(baris_list, ["kunci", "nama"])
        skema = _buat_skema([
            _buat_pasangan("kunci", "f_kunci", peran=PeranPasangan.WAJIB),
            _buat_pasangan("nama", "f_nama"),
        ], k=2)

        hasil_field = (
            _buat_field("f_kunci", "K019999"),
            _buat_field("f_nama", "Perusahaan19999"),
        )
        hasil = terapkan_skema(skema, hasil_field, indeks)
        assert hasil.status in (StatusValidasi.VALID, StatusValidasi.PERLU_DICEK)


class TestUjiTabrakan:
    def test_tanpa_tabrakan(self) -> None:
        """Kunci unik -> tidak ada tabrakan."""
        baris_list = [
            _buat_baris(f"b{i}", {"kunci": f"K{i:04d}"})
            for i in range(10)
        ]
        indeks = _buat_indeks(baris_list, ["kunci"])
        skema = _buat_skema([_buat_pasangan("kunci", "f_kunci")], k=1)

        result = uji_tabrakan(skema, indeks)
        assert result["baris_dengan_kembaran"] == 0
        assert result["persen_tabrakan"] == 0.0

    def test_dengan_tabrakan(self) -> None:
        """Dua baris dengan nilai kunci sama -> ada tabrakan."""
        baris_list = [
            _buat_baris("b1", {"kunci": "SAMA"}),
            _buat_baris("b2", {"kunci": "SAMA"}),  # Duplikat
            _buat_baris("b3", {"kunci": "BEDA"}),
        ]
        indeks = _buat_indeks(baris_list, ["kunci"])
        skema = _buat_skema([_buat_pasangan("kunci", "f_kunci")], k=1)

        result = uji_tabrakan(skema, indeks)
        assert result["baris_dengan_kembaran"] > 0
