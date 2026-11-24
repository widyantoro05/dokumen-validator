"""
tests/golden/test_golden.py - Golden tests untuk memastikan output tidak berubah.

Input contoh + hasil yang diharapkan disimpan di tests/golden/
Tes gagal bila hasil pencocokan berubah dari yang diharapkan.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from validator_dokumen.core.matcher import terapkan_skema
from validator_dokumen.core.models import (
    BarisRekap,
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

GOLDEN_DIR = Path(__file__).parent / "data"


def _pastikan_data_golden() -> None:
    """Buat data golden jika belum ada."""
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / "golden_matcher.json"
    if not path.exists():
        # Buat data golden
        data = {
            "kasus": [
                {
                    "nama": "kunci_tunggal_cocok",
                    "baris_rekap": [{"id": "b1", "data": {"kode": "K001", "nama": "Perusahaan A"}}],
                    "field_dokumen": [{"nama": "f_kode", "nilai": "K001"}],
                    "pasangan": [{"kolom": "kode", "field": "f_kode", "mode": "Persis setelah normalisasi"}],
                    "k": 1,
                    "status_diharapkan": "VALID",
                },
                {
                    "nama": "kunci_tunggal_tidak_cocok",
                    "baris_rekap": [{"id": "b1", "data": {"kode": "K001"}}],
                    "field_dokumen": [{"nama": "f_kode", "nilai": "K999"}],
                    "pasangan": [{"kolom": "kode", "field": "f_kode", "mode": "Persis setelah normalisasi"}],
                    "k": 1,
                    "status_diharapkan": "TIDAK_VALID",
                },
                {
                    "nama": "kombinasi_kunci_cocok",
                    "baris_rekap": [
                        {"id": "b1", "data": {"kode": "K001", "nama": "Perusahaan A"}},
                        {"id": "b2", "data": {"kode": "K002", "nama": "Perusahaan B"}},
                    ],
                    "field_dokumen": [
                        {"nama": "f_kode", "nilai": "K001"},
                        {"nama": "f_nama", "nilai": "Perusahaan A"},
                    ],
                    "pasangan": [
                        {"kolom": "kode", "field": "f_kode", "mode": "Persis setelah normalisasi"},
                        {"kolom": "nama", "field": "f_nama", "mode": "Persis setelah normalisasi"},
                    ],
                    "k": 2,
                    "status_diharapkan": "VALID",
                },
            ]
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class TestGoldenMatcher:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        _pastikan_data_golden()

    def _jalankan_kasus(self, kasus: dict) -> str:
        """Jalankan satu kasus golden dan kembalikan status."""
        # Buat rekapan
        baris_list = []
        for b in kasus["baris_rekap"]:
            baris_list.append(BarisRekap(
                id=b["id"],
                data=b["data"],
                sumber_file="golden.xlsx",
                sumber_sheet="Data",
                nomor_baris_asli=1,
            ))

        kolom = list(kasus["baris_rekap"][0]["data"].keys())
        tabel = TabelRekap(baris=tuple(baris_list), kolom=tuple(kolom), sumber_file="g.xlsx", hash_file="golden")
        opsi = {k: OpsiNormalisasi(abaikan_huruf_besar=True, abaikan_spasi=True) for k in kolom}
        indeks = IndeksRekap(tabel, kolom, opsi)

        # Buat field dokumen
        hasil_field: list[NilaiField] = []
        for fd in kasus["field_dokumen"]:
            nilai = fd["nilai"]
            nf = NilaiField(
                nama_field=fd["nama"],
                nilai_mentah=nilai,
                nilai_normalisasi=nilai.lower().replace(" ", ""),
                halaman=1,
                kotak=None,
                sumber=SumberData.TEKS,
                confidence=100.0,
                kandidat_lain=(),
            )
            hasil_field.append(nf)

        # Buat skema
        pasangan_list = []
        for p in kasus["pasangan"]:
            pasangan_list.append(PasanganPencocokan(
                id=str(uuid.uuid4()),
                kolom_rekap=p["kolom"],
                field_dokumen=p["field"],
                peran=PeranPasangan.POIN,
                mode=ModeCocok(p["mode"]),
                normalisasi=OpsiNormalisasi(abaikan_huruf_besar=True, abaikan_spasi=True),
            ))

        skema = SkemaPencocokan(
            id=str(uuid.uuid4()),
            nama="Golden Skema",
            pasangan=tuple(pasangan_list),
            k_minimum=kasus["k"],
            aktif=True,
        )

        hasil = terapkan_skema(skema, tuple(hasil_field), indeks)
        return hasil.status.value

    def test_semua_kasus_golden(self) -> None:
        path = GOLDEN_DIR / "golden_matcher.json"
        if not path.exists():
            pytest.skip("Data golden belum dibuat")

        data = json.loads(path.read_text(encoding="utf-8"))
        for kasus in data["kasus"]:
            status = self._jalankan_kasus(kasus)
            assert status == kasus["status_diharapkan"], (
                f"Kasus '{kasus['nama']}': "
                f"diharapkan {kasus['status_diharapkan']}, dapat {status}"
            )
