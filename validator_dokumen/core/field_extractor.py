"""
core/field_extractor.py - Ekstraktor field dari dokumen PDF.

Mendukung 4 cara ambil yang didefinisikan pengguna:
(a) label - cari label dengan sinonim, ambil nilai setelah label
(b) pola - regex dengan grup penangkap
(c) area - koordinat relatif halaman
(d) kolom_tabel - kolom dalam tabel PDF

Semua nama field bersifat dinamis (dari definisi pengguna).
"""

from __future__ import annotations

import re
from typing import Any

from validator_dokumen.core.models import (
    DefinisiField,
    NilaiField,
    OpsiNormalisasi,
    SumberData,
)
from validator_dokumen.core.normalizer import normalisasi_teks


def _cari_label(
    teks_baris: list[str],
    label: str,
    sinonim: list[str],
    pola_penghenti: str | None,
) -> str | None:
    """
    Cari label (dan sinonimnya) dalam baris teks, ambil nilai setelah label.
    Urutkan label dari yang terpanjang agar nama spesifik lebih diprioritaskan.
    """
    semua_label = sorted([label, *list(sinonim)], key=len, reverse=True)
    pola_penghenti_compiled = re.compile(pola_penghenti, re.IGNORECASE) if pola_penghenti else None

    for i, baris in enumerate(teks_baris):
        for lbl in semua_label:
            pola_lbl = re.compile(r"\b" + re.escape(lbl) + r"\b[:\-=\s]*", re.IGNORECASE)
            m = pola_lbl.search(baris)
            if not m:
                continue

            # Ambil nilai setelah label di baris yang sama
            setelah_label = baris[m.end() :].strip()
            if setelah_label:
                if pola_penghenti_compiled:
                    m_stop = pola_penghenti_compiled.search(setelah_label)
                    if m_stop:
                        setelah_label = setelah_label[: m_stop.start()].strip()
                if setelah_label:
                    return setelah_label

            # Jika baris berikutnya ada dan baris ini murni header (setelah_label kosong),
            # ambil baris berikutnya jika tidak mengandung label lain
            if i + 1 < len(teks_baris):
                baris_berikut = teks_baris[i + 1].strip()
                if pola_penghenti_compiled:
                    m_stop = pola_penghenti_compiled.search(baris_berikut)
                    if m_stop:
                        baris_berikut = baris_berikut[: m_stop.start()].strip()
                if baris_berikut and not any(
                    re.search(r"\b" + re.escape(l) + r"\b", baris_berikut, re.IGNORECASE)
                    for l in semua_label
                ):
                    return baris_berikut

    return None


def ekstrak_field_label(
    teks: str,
    parameter: dict[str, Any],
) -> list[str]:
    """
    Ekstrak field dengan cara 'label'.

    Parameter yang diharapkan:
    - label: str - label utama
    - sinonim: list[str] - sinonim label (opsional)
    - pola_penghenti: str - regex untuk berhenti (opsional)
    """
    label_raw = parameter.get("label", "")
    if isinstance(label_raw, list):
        label = label_raw[0] if label_raw else ""
        sinonim = list(parameter.get("sinonim", [])) + label_raw[1:]
    else:
        label = str(label_raw)
        sinonim = list(parameter.get("sinonim", []))

    pola_penghenti = parameter.get("pola_penghenti")

    if not label:
        return []

    baris_list = teks.split("\n")
    nilai = _cari_label(baris_list, label, sinonim, pola_penghenti)

    return [nilai] if nilai else []


def ekstrak_field_pola(
    teks: str,
    parameter: dict[str, Any],
) -> list[str]:
    """
    Ekstrak field dengan cara 'pola' (regex).

    Parameter yang diharapkan:
    - pola: str - ekspresi regex dengan grup penangkap
    - grup: int - indeks grup yang diambil (default 1)
    - flag_case_insensitive: bool
    """
    pola_str = parameter.get("pola", "")
    grup = parameter.get("grup", 1)
    case_insensitive = parameter.get("flag_case_insensitive", True)

    if not pola_str:
        return []

    flags = re.IGNORECASE if case_insensitive else 0
    try:
        pola_compiled = re.compile(pola_str, flags)
    except re.error:
        return []

    hasil = pola_compiled.findall(teks)
    nilai_list: list[str] = []
    for m in hasil:
        if isinstance(m, tuple):
            # Jika ada grup, ambil grup yang ditentukan
            if grup - 1 < len(m):
                v = m[grup - 1]
                if v:
                    nilai_list.append(v.strip())
        else:
            if m:
                nilai_list.append(m.strip())

    return nilai_list


def ekstrak_field_area(
    halaman_data: dict[str, Any],
    parameter: dict[str, Any],
    lebar_halaman: float,
    tinggi_halaman: float,
) -> list[str]:
    """
    Ekstrak field dari area/koordinat relatif halaman.

    Parameter yang diharapkan:
    - x0_persen, y0_persen, x1_persen, y1_persen: float (0-100)
    """
    x0_p = parameter.get("x0_persen", 0.0) / 100.0
    y0_p = parameter.get("y0_persen", 0.0) / 100.0
    x1_p = parameter.get("x1_persen", 100.0) / 100.0
    y1_p = parameter.get("y1_persen", 100.0) / 100.0

    x0 = x0_p * lebar_halaman
    y0 = y0_p * tinggi_halaman
    x1 = x1_p * lebar_halaman
    y1 = y1_p * tinggi_halaman

    kata_dalam_area: list[str] = []
    for kata in halaman_data.get("kata_kata", []):
        kx0, ky0, kx1, ky1 = kata.get("kotak", (0, 0, 0, 0))
        # Pusat kata harus dalam area
        pusat_x = (kx0 + kx1) / 2
        pusat_y = (ky0 + ky1) / 2
        if x0 <= pusat_x <= x1 and y0 <= pusat_y <= y1:
            kata_dalam_area.append(kata["teks"])

    if kata_dalam_area:
        return [" ".join(kata_dalam_area)]
    return []


def ekstrak_semua_field(
    definisi_list: list[DefinisiField],
    hasil_baca_pdf: dict[str, Any],
) -> tuple[NilaiField, ...]:
    """
    Ekstrak semua field yang didefinisikan dari hasil pembacaan PDF.

    Args:
        definisi_list: Daftar definisi field dari profil.
        hasil_baca_pdf: Hasil dari baca_pdf().

    Returns:
        Tuple NilaiField untuk semua field yang berhasil diekstrak.
    """
    hasil: list[NilaiField] = []
    opsi_default = OpsiNormalisasi()

    # Gabungkan teks semua halaman
    semua_halaman = hasil_baca_pdf.get("halaman", [])
    "\n\n".join(h.get("teks", "") for h in semua_halaman)

    for defn in definisi_list:
        nilai_kandidat: list[str] = []
        halaman_ditemukan = 1
        kotak_ditemukan: tuple[float, float, float, float] | None = None
        sumber = SumberData.TEKS
        confidence = 100.0
        meragukan = False

        # Cari di tiap halaman
        for hal_data in semua_halaman:
            teks_hal = hal_data.get("teks", "")
            hal_sumber = hal_data.get("sumber", SumberData.TEKS.value)
            hal_conf = hal_data.get("confidence_rata", 100.0)

            kandidat_hal: list[str] = []

            if defn.cara_ambil == "label":
                kandidat_hal = ekstrak_field_label(teks_hal, defn.parameter)

            elif defn.cara_ambil == "pola":
                kandidat_hal = ekstrak_field_pola(teks_hal, defn.parameter)

            elif defn.cara_ambil == "area":
                # Estimasi lebar/tinggi halaman (default A4 72dpi)
                lebar = defn.parameter.get("lebar_halaman", 595.0)
                tinggi = defn.parameter.get("tinggi_halaman", 842.0)
                kandidat_hal = ekstrak_field_area(hal_data, defn.parameter, lebar, tinggi)

            elif defn.cara_ambil == "kolom_tabel":
                kandidat_hal = _ekstrak_dari_tabel(teks_hal, defn.parameter)

            if kandidat_hal:
                nilai_kandidat.extend(kandidat_hal)
                halaman_ditemukan = hal_data.get("nomor", 1)
                sumber = (
                    SumberData(hal_sumber)
                    if hal_sumber in [s.value for s in SumberData]
                    else SumberData.TEKS
                )
                confidence = hal_conf
                meragukan = hal_data.get("meragukan", False)
                break  # Ambil dari halaman pertama yang berhasil

        nilai_mentah = nilai_kandidat[0] if nilai_kandidat else ""
        nilai_norm = normalisasi_teks(nilai_mentah, opsi_default) if nilai_mentah else ""

        nf = NilaiField(
            nama_field=defn.nama,
            nilai_mentah=nilai_mentah,
            nilai_normalisasi=nilai_norm,
            halaman=halaman_ditemukan,
            kotak=kotak_ditemukan,
            sumber=sumber,
            confidence=confidence,
            kandidat_lain=tuple(nilai_kandidat[1:]),
            meragukan=meragukan,
        )
        hasil.append(nf)

    return tuple(hasil)


def _ekstrak_dari_tabel(teks: str, parameter: dict[str, Any]) -> list[str]:
    """
    Ekstrak nilai dari kolom tabel dalam teks.
    Mencari header kolom lalu ambil nilai di bawahnya.
    """
    nama_kolom = parameter.get("nama_kolom", "")
    if not nama_kolom:
        return []

    baris_list = teks.split("\n")
    for i, baris in enumerate(baris_list):
        if nama_kolom.lower() in baris.lower():
            # Coba ambil nilai dari baris berikutnya
            if i + 1 < len(baris_list):
                nilai = baris_list[i + 1].strip()
                if nilai:
                    return [nilai]
    return []
