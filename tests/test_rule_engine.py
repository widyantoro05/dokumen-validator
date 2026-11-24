"""
tests/test_rule_engine.py - Tes unit untuk modul rule_engine.
"""

from __future__ import annotations

import pytest

from validator_dokumen.core.models import (
    AksiKondisional,
    AturanField,
    BarisRekap,
    KondisiJikaMaka,
    NilaiField,
    OpsiNormalisasi,
    SumberData,
)
from validator_dokumen.core.rule_engine import (
    evaluasi_aturan_field,
    evaluasi_semua_aturan_field,
    evaluasi_kondisi_jika_maka,
)


def _buat_nilai_field(nama: str, nilai: str) -> NilaiField:
    return NilaiField(
        nama_field=nama,
        nilai_mentah=nilai,
        nilai_normalisasi=nilai.lower(),
        halaman=1,
        kotak=None,
        sumber=SumberData.TEKS,
        confidence=100.0,
        kandidat_lain=(),
    )


def _buat_aturan(
    tipe: str,
    field_nama: str = "field_tes",
    parameter: dict | None = None,
    pesan_kustom: str = "",
) -> AturanField:
    import uuid
    return AturanField(
        id=str(uuid.uuid4()),
        field_nama=field_nama,
        tipe_aturan=tipe,
        parameter=parameter or {},
        aktif=True,
        pesan_kustom=pesan_kustom,
    )


class TestAturanWajibAda:
    def test_nilai_ada_lolos(self) -> None:
        aturan = _buat_aturan("wajib_ada")
        nilai_field = _buat_nilai_field("field_tes", "nilai_ok")
        lolos, pesan, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is True
        assert pesan == ""

    def test_nilai_kosong_gagal(self) -> None:
        aturan = _buat_aturan("wajib_ada")
        nilai_field = _buat_nilai_field("field_tes", "")
        lolos, pesan, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is False
        assert pesan != ""

    def test_field_tidak_ada_gagal(self) -> None:
        aturan = _buat_aturan("wajib_ada")
        lolos, pesan, _ = evaluasi_aturan_field(aturan, None)
        assert lolos is False

    def test_pesan_kustom(self) -> None:
        aturan = _buat_aturan("wajib_ada", pesan_kustom="Pesan kustom!")
        lolos, pesan, _ = evaluasi_aturan_field(aturan, None)
        assert pesan == "Pesan kustom!"


class TestAturanFormatPola:
    def test_angka_saja_lolos(self) -> None:
        aturan = _buat_aturan("format_pola", parameter={"pola": "angka_saja"})
        nilai_field = _buat_nilai_field("f", "12345")
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is True

    def test_angka_saja_gagal_ada_huruf(self) -> None:
        aturan = _buat_aturan("format_pola", parameter={"pola": "angka_saja"})
        nilai_field = _buat_nilai_field("f", "123A5")
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is False

    def test_pola_regex_kustom(self) -> None:
        aturan = _buat_aturan("format_pola", parameter={"pola": r"^IZN-\d{4}-[A-Z]{3}$"})
        nilai_field = _buat_nilai_field("f", "IZN-1234-ABC")
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is True

    def test_template_nib_13_digit(self) -> None:
        aturan = _buat_aturan("format_pola", parameter={"pola": "nib"})
        nilai_field = _buat_nilai_field("f", "1234567890123")  # 13 digit
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is True

    def test_template_nib_bukan_13_digit(self) -> None:
        aturan = _buat_aturan("format_pola", parameter={"pola": "nib"})
        nilai_field = _buat_nilai_field("f", "123")  # Bukan 13 digit
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is False


class TestAturanPanjang:
    def test_panjang_ok(self) -> None:
        aturan = _buat_aturan("panjang", parameter={"min": 5, "max": 10})
        nilai_field = _buat_nilai_field("f", "1234567")
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is True

    def test_terlalu_pendek(self) -> None:
        aturan = _buat_aturan("panjang", parameter={"min": 10})
        nilai_field = _buat_nilai_field("f", "123")
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is False

    def test_terlalu_panjang(self) -> None:
        aturan = _buat_aturan("panjang", parameter={"min": 1, "max": 5})
        nilai_field = _buat_nilai_field("f", "1234567890")
        lolos, _, _ = evaluasi_aturan_field(aturan, nilai_field)
        assert lolos is False


class TestAturanTidakAktif:
    def test_aturan_nonaktif_selalu_lolos(self) -> None:
        import uuid
        aturan = AturanField(
            id=str(uuid.uuid4()),
            field_nama="f",
            tipe_aturan="wajib_ada",
            parameter={},
            aktif=False,
            pesan_kustom="",
        )
        lolos, _, _ = evaluasi_aturan_field(aturan, None)
        assert lolos is True


class TestKondisionalJikaMaka:
    def test_kondisi_tidak_terpenuhi(self) -> None:
        """Kondisi JIKA tidak terpenuhi -> aksi tidak dijalankan."""
        import uuid
        kondisi = KondisiJikaMaka(
            id=str(uuid.uuid4()),
            kondisi=({"sumber": "field", "nama": "jenis", "operator": "sama dengan", "nilai": "manufaktur"},),
            aksi=AksiKondisional.TANDAI_TIDAK_VALID,
            parameter_aksi={},
            aktif=True,
            pesan_kustom="Harus tidak valid",
        )
        hasil_field = (_buat_nilai_field("jenis", "perdagangan"),)
        hasil = evaluasi_kondisi_jika_maka([kondisi], hasil_field, None, [])
        # Kondisi tidak terpenuhi -> tidak ada masalah
        masalah = [pesan for terpicu, _, pesan, _ in hasil if terpicu]
        assert len(masalah) == 0

    def test_aturan_salah_satu_dan_mengandung(self) -> None:
        aturan1 = _buat_aturan("salah_satu", parameter={"pilihan": ["PT Maju", "CV Berkah"]})
        nf1 = _buat_nilai_field("f", "PT Maju")
        lolos, _, _ = evaluasi_aturan_field(aturan1, nf1)
        assert lolos is True

        baris_rekap = BarisRekap("b1", {"kategori": "Resiko Rendah"}, "s.xlsx", "Sheet1", 1)
        aturan2 = _buat_aturan("salah_satu", parameter={"dari_kolom_rekap": "kategori"})
        nf2 = _buat_nilai_field("f", "Resiko Rendah")
        lolos, _, _ = evaluasi_aturan_field(aturan2, nf2, baris_rekap)
        assert lolos is True

        aturan3 = _buat_aturan("mengandung", parameter={"teks": "Jaya"})
        lolos, _, _ = evaluasi_aturan_field(aturan3, _buat_nilai_field("f", "PT Maju Jaya"))
        assert lolos is True

        aturan4 = _buat_aturan("tidak_mengandung", parameter={"teks": "Palsu"})
        lolos, _, _ = evaluasi_aturan_field(aturan4, _buat_nilai_field("f", "Dokumen Asli"))
        assert lolos is True

    def test_aturan_tanggal_logika(self) -> None:
        import datetime
        tgl_depan = (datetime.date.today() + datetime.timedelta(days=100)).strftime("%d/%m/%Y")
        aturan = _buat_aturan("tanggal_belum_kedaluwarsa")
        lolos, _, _ = evaluasi_aturan_field(aturan, _buat_nilai_field("f", tgl_depan))
        assert lolos is True

        tgl_lampau = "01/01/2020"
        lolos2, _, _ = evaluasi_aturan_field(aturan, _buat_nilai_field("f", tgl_lampau))
        assert lolos2 is False

    def test_kondisi_jika_maka_lengkap(self) -> None:
        import uuid
        baris = BarisRekap("b1", {"status_rekap": "AKTIF", "kuota": "100"}, "s.xlsx", "S", 1)

        # JIKA field jenis berisi 'khusus' DAN rekap kuota > 50 MAKA kolom status_rekap harus bernilai AKTIF
        kondisi = KondisiJikaMaka(
            id=str(uuid.uuid4()),
            kondisi=(
                {"sumber": "field", "nama": "jenis", "operator": "berisi", "nilai": "khusus", "hubungan": "AND"},
                {"sumber": "rekap", "nama": "kuota", "operator": ">", "nilai": "50", "hubungan": "AND"},
            ),
            aksi=AksiKondisional.KOLOM_REKAP_HARUS_BERNILAI,
            parameter_aksi={"kolom": "status_rekap", "nilai": "AKTIF"},
            aktif=True,
        )
        fields = (_buat_nilai_field("jenis", "Izin Khusus Perdagangan"),)
        res = evaluasi_kondisi_jika_maka([kondisi], fields, baris, [])
        assert len(res) == 1
        terpicu_masalah, aksi, pesan, _ = res[0]
        assert not terpicu_masalah  # Sukses (tidak ada masalah)

        # FIELD_HARUS_COCOK_KOLOM
        kondisi2 = KondisiJikaMaka(
            id=str(uuid.uuid4()),
            kondisi=({"sumber": "field", "nama": "jenis", "operator": "tidak kosong", "nilai": ""},),
            aksi=AksiKondisional.FIELD_HARUS_COCOK_KOLOM,
            parameter_aksi={"field_nama": "jenis", "kolom_nama": "status_rekap"},
            aktif=True,
        )
        res2 = evaluasi_kondisi_jika_maka([kondisi2], fields, baris, [])
        terpicu2, _, pesan2, _ = res2[0]
        assert terpicu2 is True  # Karena 'Izin Khusus Perdagangan' != 'AKTIF'

    def test_aturan_tipe_lain(self) -> None:
        # tanggal_terbit_lebih_kecil
        at1 = _buat_aturan("tanggal_terbit_lebih_kecil", parameter={"field_berakhir": "tgl_akhir"})
        lolos, _, _ = evaluasi_aturan_field(at1, _buat_nilai_field("f", "01/01/2025"))
        assert lolos is True

        # tipe tidak dikenal
        at2 = _buat_aturan("tipe_aneh")
        lolos2, _, _ = evaluasi_aturan_field(at2, _buat_nilai_field("f", "val"))
        assert lolos2 is True

    def test_operator_kondisi_tambahan(self) -> None:
        import uuid
        baris = BarisRekap("b1", {"nilai_angka": "25", "catatan": "vip,member"}, "s.xlsx", "S", 1)

        # Operator <
        k1 = KondisiJikaMaka(
            id=str(uuid.uuid4()),
            kondisi=({"sumber": "rekap", "nama": "nilai_angka", "operator": "<", "nilai": "50"},),
            aksi=AksiKondisional.WAJIB_ADA_FIELD,
            parameter_aksi={"field_nama": "f_vip"},
            aktif=True,
        )
        res1 = evaluasi_kondisi_jika_maka([k1], (_buat_nilai_field("f_vip", "ada"),), baris, [])
        assert not res1[0][0]  # Berhasil

        # Operator kosong & termasuk daftar
        k2 = KondisiJikaMaka(
            id=str(uuid.uuid4()),
            kondisi=(
                {"sumber": "field", "nama": "kosong_f", "operator": "kosong", "nilai": "", "hubungan": "AND"},
                {"sumber": "rekap", "nama": "catatan", "operator": "termasuk daftar", "nilai": ["vip,member"], "hubungan": "AND"},
            ),
            aksi=AksiKondisional.TANDAI_TIDAK_VALID,
            parameter_aksi={},
            aktif=True,
        )
        res2 = evaluasi_kondisi_jika_maka([k2], (_buat_nilai_field("kosong_f", ""),), baris, [])
        assert res2[0][0]  # Terpicu tidak valid
