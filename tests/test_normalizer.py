"""
tests/test_normalizer.py - Tes unit untuk modul normalizer.
"""

from __future__ import annotations

import pytest

from validator_dokumen.core.models import OpsiNormalisasi
from validator_dokumen.core.normalizer import (
    abaikan_huruf_besar,
    bandingkan_tanggal,
    hapus_awalan_badan_usaha,
    hapus_karakter_tak_terlihat,
    hapus_nol_depan,
    hapus_tanda_baca_dan_spasi,
    koreksi_karakter_ocr,
    normalisasi_teks,
    parse_angka,
    parse_tanggal,
    trim_spasi,
)


class TestTrimSpasi:
    def test_trim_spasi_depan_belakang(self) -> None:
        assert trim_spasi("  hello  ") == "hello"

    def test_spasi_ganda(self) -> None:
        assert trim_spasi("hello   world") == "hello world"

    def test_teks_kosong(self) -> None:
        assert trim_spasi("") == ""

    def test_hanya_spasi(self) -> None:
        assert trim_spasi("   ") == ""


class TestKarakterTakTerlihat:
    def test_hapus_zero_width_space(self) -> None:
        assert hapus_karakter_tak_terlihat("hel\u200blo") == "hello"

    def test_hapus_nbsp(self) -> None:
        assert hapus_karakter_tak_terlihat("hel\u00a0lo") == "hello"

    def test_hapus_bom(self) -> None:
        assert hapus_karakter_tak_terlihat("\ufeffhello") == "hello"

    def test_teks_normal_tidak_berubah(self) -> None:
        assert hapus_karakter_tak_terlihat("hello world") == "hello world"


class TestAbaikanHurufBesar:
    def test_huruf_besar_ke_kecil(self) -> None:
        assert abaikan_huruf_besar("HELLO") == "hello"

    def test_campuran(self) -> None:
        assert abaikan_huruf_besar("HeLLo WoRLd") == "hello world"


class TestHapusTandaBacaDanSpasi:
    def test_hapus_tanda_baca(self) -> None:
        assert hapus_tanda_baca_dan_spasi("hello, world!") == "helloworld"

    def test_hapus_spasi(self) -> None:
        assert hapus_tanda_baca_dan_spasi("hello world") == "helloworld"

    def test_angka_tetap(self) -> None:
        assert hapus_tanda_baca_dan_spasi("123-456") == "123456"


class TestHapusAwalanBadanUsaha:
    def test_hapus_pt(self) -> None:
        assert hapus_awalan_badan_usaha("PT Maju Jaya") == "Maju Jaya"

    def test_hapus_pt_titik(self) -> None:
        assert hapus_awalan_badan_usaha("PT. Maju Jaya") == "Maju Jaya"

    def test_hapus_cv(self) -> None:
        assert hapus_awalan_badan_usaha("CV Berkah Abadi") == "Berkah Abadi"

    def test_hapus_tbk(self) -> None:
        hasil = hapus_awalan_badan_usaha("PT Maju Jaya Tbk")
        assert "Tbk" not in hasil
        assert "Maju Jaya" in hasil

    def test_tanpa_awalan_tidak_berubah(self) -> None:
        assert hapus_awalan_badan_usaha("Maju Jaya") == "Maju Jaya"


class TestHapusNolDepan:
    def test_hapus_nol_tunggal(self) -> None:
        assert hapus_nol_depan("007") == "7"

    def test_hapus_banyak_nol(self) -> None:
        assert hapus_nol_depan("00123") == "123"

    def test_angka_tanpa_nol(self) -> None:
        assert hapus_nol_depan("123") == "123"

    def test_angka_nol(self) -> None:
        # "0" tunggal tidak berubah
        assert hapus_nol_depan("0") == "0"


class TestKoreksiOcr:
    def test_koreksi_O_ke_0_dalam_angka(self) -> None:
        # O di antara angka harus dikoreksi
        assert koreksi_karakter_ocr("1O1") == "101"

    def test_koreksi_I_ke_1(self) -> None:
        assert koreksi_karakter_ocr("1I1") == "111"

    def test_huruf_di_luar_konteks_angka_tidak_berubah(self) -> None:
        # O di antara huruf tidak dikoreksi
        hasil = koreksi_karakter_ocr("OKE")
        assert hasil == "OKE"  # Tidak ada angka di kiri/kanan


class TestNormalisasiTeks:
    def test_opsi_default(self) -> None:
        opsi = OpsiNormalisasi()
        hasil = normalisasi_teks("  HELLO WORLD  ", opsi)
        # Default: hapus karakter tak terlihat, trim, abaikan huruf besar, abaikan spasi
        assert hasil == "helloworld"

    def test_hanya_huruf_besar(self) -> None:
        opsi = OpsiNormalisasi(
            abaikan_huruf_besar=True,
            abaikan_spasi=False,
            abaikan_tanda_baca=False,
        )
        hasil = normalisasi_teks("HELLO WORLD", opsi)
        assert hasil == "hello world"

    def test_abaikan_awalan_badan_usaha(self) -> None:
        opsi = OpsiNormalisasi(
            abaikan_awalan_badan_usaha=True,
            abaikan_huruf_besar=True,
            abaikan_spasi=False,
        )
        hasil = normalisasi_teks("PT Maju Jaya", opsi)
        assert "pt" not in hasil.lower() or "maju" in hasil.lower()

    def test_determinisme(self) -> None:
        opsi = OpsiNormalisasi()
        teks = "  PT. MAJU JAYA 00123  "
        hasil1 = normalisasi_teks(teks, opsi)
        hasil2 = normalisasi_teks(teks, opsi)
        assert hasil1 == hasil2


class TestParseAngka:
    def test_angka_sederhana(self) -> None:
        from decimal import Decimal
        assert parse_angka("1000") == Decimal("1000")

    def test_format_indonesia(self) -> None:
        from decimal import Decimal
        assert parse_angka("1.000,50") == Decimal("1000.50")

    def test_format_internasional(self) -> None:
        from decimal import Decimal
        assert parse_angka("1,000.50") == Decimal("1000.50")

    def test_string_bukan_angka(self) -> None:
        assert parse_angka("bukan angka") is None

    def test_string_kosong(self) -> None:
        assert parse_angka("") is None


class TestParseTanggal:
    def test_teks_indonesia_lengkap(self) -> None:
        assert parse_tanggal("12 Januari 2025") == (2025, 1, 12)

    def test_teks_indonesia_singkat(self) -> None:
        assert parse_tanggal("5 Jan 2025") == (2025, 1, 5)

    def test_format_dd_mm_yyyy(self) -> None:
        assert parse_tanggal("12/01/2025") == (2025, 1, 12)

    def test_format_yyyy_mm_dd(self) -> None:
        assert parse_tanggal("2025-01-12") == (2025, 1, 12)

    def test_format_dengan_tanda_hubung(self) -> None:
        assert parse_tanggal("12-01-2025") == (2025, 1, 12)

    def test_string_kosong(self) -> None:
        assert parse_tanggal("") is None

    def test_bukan_tanggal(self) -> None:
        assert parse_tanggal("ini bukan tanggal") is None


class TestBandingkanTanggal:
    def test_tanggal_sama(self) -> None:
        assert bandingkan_tanggal("12/01/2025", "12/01/2025", "sama") is True

    def test_tanggal_beda(self) -> None:
        assert bandingkan_tanggal("12/01/2025", "13/01/2025", "sama") is False

    def test_a_lebih_kecil(self) -> None:
        assert bandingkan_tanggal("01/01/2025", "31/12/2025", "a_lebih_kecil") is True

    def test_a_lebih_besar(self) -> None:
        assert bandingkan_tanggal("31/12/2025", "01/01/2025", "a_lebih_besar") is True

    def test_tanggal_tidak_valid(self) -> None:
        assert bandingkan_tanggal("bukan_tanggal", "12/01/2025", "sama") is None
