"""
core/matcher.py - Mesin pencocokan dokumen dengan tabel rekapan.

Implementasi algoritma pencocokan K dari N yang efisien dengan indeks terbalik.
Semua kolom/field bersifat dinamis - tidak ada yang di-hardcode.
Determinisme terjamin: input sama menghasilkan output sama.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from validator_dokumen.core.constants import (
    FUZZY_NEAR_MISS_DECREMENT,
)
from validator_dokumen.core.decision_trace import (
    jejak_normalisasi,
    jejak_pencocokan,
)
from validator_dokumen.core.models import (
    BarisRekap,
    HasilPasangan,
    HasilSkema,
    JikaAdaTidakCocok,
    LangkahJejak,
    ModeCocok,
    NilaiField,
    OpsiNormalisasi,
    PasanganPencocokan,
    PeranPasangan,
    SkemaPencocokan,
    StatusValidasi,
)
from validator_dokumen.core.normalizer import (
    bandingkan_tanggal,
    normalisasi_teks,
    parse_angka,
)
from validator_dokumen.core.recap_table import IndeksRekap


def _dapatkan_nilai_field(
    field_nama: str,
    hasil_field: tuple[NilaiField, ...],
) -> NilaiField | None:
    """Dapatkan NilaiField berdasarkan nama field."""
    for nf in hasil_field:
        if nf.nama_field == field_nama:
            return nf
    return None


def _normalisasi_untuk_pasangan(
    nilai: str,
    opsi: OpsiNormalisasi,
    opsi_aktif: list[str],
) -> str:
    """Normalisasi nilai dan catat opsi aktif untuk jejak."""
    return normalisasi_teks(nilai, opsi)


def _daftar_opsi_aktif(opsi: OpsiNormalisasi) -> list[str]:
    """Buat daftar nama opsi yang aktif untuk tampilan jejak."""
    aktif = []
    if opsi.abaikan_huruf_besar:
        aktif.append("huruf besar diabaikan")
    if opsi.abaikan_spasi:
        aktif.append("spasi diabaikan")
    if opsi.abaikan_tanda_baca:
        aktif.append("tanda baca diabaikan")
    if opsi.abaikan_awalan_badan_usaha:
        aktif.append("awalan badan usaha diabaikan")
    if opsi.abaikan_nol_depan:
        aktif.append("nol di depan diabaikan")
    if opsi.koreksi_ocr:
        aktif.append("koreksi OCR")
    if opsi.hapus_karakter_tak_terlihat:
        aktif.append("karakter tak terlihat dihapus")
    return aktif


def cocokkan_pasangan(
    pasangan: PasanganPencocokan,
    nilai_dokumen_mentah: str,
    nilai_rekap_mentah: str,
    meragukan: bool = False,
) -> HasilPasangan:
    """
    Jalankan pencocokan satu pasangan kolom rekapan <-> field dokumen.

    Args:
        pasangan: Definisi pasangan pencocokan.
        nilai_dokumen_mentah: Nilai mentah dari dokumen.
        nilai_rekap_mentah: Nilai mentah dari rekapan.
        meragukan: True jika dari OCR confidence rendah.

    Returns:
        HasilPasangan dengan jejak keputusan.
    """
    jejak: list[LangkahJejak] = []
    opsi = pasangan.normalisasi
    opsi_aktif = _daftar_opsi_aktif(opsi)

    # Langkah 1: normalisasi
    nilai_dok_norm = normalisasi_teks(nilai_dokumen_mentah, opsi)
    nilai_rek_norm = normalisasi_teks(nilai_rekap_mentah, opsi)

    jejak.append(jejak_normalisasi(nilai_dokumen_mentah, nilai_dok_norm, opsi_aktif))

    # Langkah 2: pencocokan berdasarkan mode
    cocok = False
    skor_mirip: float | None = None

    if pasangan.mode == ModeCocok.PERSIS:
        cocok = nilai_dokumen_mentah == nilai_rekap_mentah
        jejak.append(jejak_pencocokan(nilai_dokumen_mentah, nilai_rekap_mentah, "Persis", cocok))

    elif pasangan.mode == ModeCocok.PERSIS_NORMALISASI:
        cocok = nilai_dok_norm == nilai_rek_norm
        jejak.append(
            jejak_pencocokan(nilai_dok_norm, nilai_rek_norm, "Persis setelah normalisasi", cocok)
        )

    elif pasangan.mode == ModeCocok.MIRIP:
        try:
            from rapidfuzz import fuzz  # type: ignore[import-untyped]

            skor = fuzz.token_sort_ratio(nilai_dok_norm, nilai_rek_norm)
            skor_mirip = float(skor)
            cocok = skor_mirip >= pasangan.ambang_mirip
        except ImportError:
            # Fallback ke persis jika rapidfuzz tidak ada
            cocok = nilai_dok_norm == nilai_rek_norm
            skor_mirip = 100.0 if cocok else 0.0
        jejak.append(
            jejak_pencocokan(
                nilai_dok_norm,
                nilai_rek_norm,
                f"Mirip (ambang {pasangan.ambang_mirip:.0f}%)",
                cocok,
                skor_mirip,
            )
        )

    elif pasangan.mode == ModeCocok.MENGANDUNG:
        cocok = nilai_rek_norm in nilai_dok_norm or nilai_dok_norm in nilai_rek_norm
        jejak.append(jejak_pencocokan(nilai_dok_norm, nilai_rek_norm, "Mengandung", cocok))

    elif pasangan.mode == ModeCocok.DIAWALI:
        cocok = nilai_dok_norm.startswith(nilai_rek_norm)
        jejak.append(jejak_pencocokan(nilai_dok_norm, nilai_rek_norm, "Diawali dengan", cocok))

    elif pasangan.mode == ModeCocok.NUMERIK:
        angka_dok = parse_angka(nilai_dokumen_mentah)
        angka_rek = parse_angka(nilai_rekap_mentah)
        if angka_dok is not None and angka_rek is not None:
            selisih = abs(angka_dok - angka_rek)
            toleransi = Decimal(str(pasangan.toleransi_numerik))
            cocok = selisih <= toleransi
            jejak.append(
                jejak_pencocokan(
                    str(angka_dok),
                    str(angka_rek),
                    f"Numerik (toleransi {pasangan.toleransi_numerik})",
                    cocok,
                )
            )
        else:
            cocok = False
            jejak.append(
                jejak_pencocokan(
                    nilai_dokumen_mentah,
                    nilai_rekap_mentah,
                    "Numerik (gagal parse)",
                    False,
                )
            )

    elif pasangan.mode == ModeCocok.TANGGAL_SAMA:
        hasil_tgl = bandingkan_tanggal(nilai_dokumen_mentah, nilai_rekap_mentah, "sama")
        cocok = hasil_tgl is True
        jejak.append(
            jejak_pencocokan(
                nilai_dokumen_mentah,
                nilai_rekap_mentah,
                "Tanggal sama persis",
                cocok,
            )
        )

    elif pasangan.mode == ModeCocok.TANGGAL_DOKUMEN_LEBIH_KECIL:
        hasil_tgl = bandingkan_tanggal(nilai_dokumen_mentah, nilai_rekap_mentah, "a_lebih_kecil")
        cocok = hasil_tgl is True
        jejak.append(
            jejak_pencocokan(
                nilai_dokumen_mentah,
                nilai_rekap_mentah,
                "Tanggal dokumen <= rekapan",
                cocok,
            )
        )

    elif pasangan.mode == ModeCocok.TANGGAL_DOKUMEN_LEBIH_BESAR:
        hasil_tgl = bandingkan_tanggal(nilai_dokumen_mentah, nilai_rekap_mentah, "a_lebih_besar")
        cocok = hasil_tgl is True
        jejak.append(
            jejak_pencocokan(
                nilai_dokumen_mentah,
                nilai_rekap_mentah,
                "Tanggal dokumen >= rekapan",
                cocok,
            )
        )

    # Pesan kesalahan
    pesan = ""
    if not cocok:
        pesan = pasangan.pesan_kesalahan_kustom or (
            f"[{pasangan.field_dokumen}] "
            f'Nilai "{nilai_dokumen_mentah}" tidak cocok dengan rekapan "{nilai_rekap_mentah}" '
            f"(mode: {pasangan.mode.value})"
        )

    return HasilPasangan(
        pasangan_id=pasangan.id,
        kolom_rekap=pasangan.kolom_rekap,
        field_dokumen=pasangan.field_dokumen,
        nilai_dokumen=nilai_dokumen_mentah,
        nilai_rekap=nilai_rekap_mentah,
        cocok=cocok,
        skor_mirip=skor_mirip,
        meragukan=meragukan,
        jejak=tuple(jejak),
        pesan_kesalahan=pesan,
    )


def terapkan_skema(
    skema: SkemaPencocokan,
    hasil_field: tuple[NilaiField, ...],
    indeks: IndeksRekap,
) -> HasilSkema:
    """
    Terapkan satu skema pencocokan terhadap field dokumen.
    Menggunakan algoritma K dari N dengan indeks terbalik.

    Args:
        skema: Skema pencocokan.
        hasil_field: Field yang diekstrak dari dokumen.
        indeks: Indeks terbalik dari tabel rekapan.

    Returns:
        HasilSkema dengan baris terbaik atau status gagal.
    """
    if not skema.aktif:
        return HasilSkema(
            skema_id=skema.id,
            skema_nama=skema.nama,
            baris_rekap_id=None,
            baris_rekap_nomor=None,
            status=StatusValidasi.TIDAK_VALID,
            alasan="Skema dinonaktifkan.",
        )

    pasangan_list = list(skema.pasangan)
    if not pasangan_list:
        return HasilSkema(
            skema_id=skema.id,
            skema_nama=skema.nama,
            baris_rekap_id=None,
            baris_rekap_nomor=None,
            status=StatusValidasi.TIDAK_VALID,
            alasan="Skema tidak punya pasangan.",
        )

    tabel = indeks.tabel

    # ── Langkah 1: Kumpulkan kandidat baris per pasangan ─────────────────────
    # Gunakan Counter untuk menghitung berapa pasangan yang cocok per baris
    skor_baris: Counter[str] = Counter()
    skor_bobot: dict[str, float] = {}

    # Lacak baris yang gagal pada pasangan WAJIB
    gagal_wajib: set[str] = set()  # id_baris yang gagal di pasangan Wajib

    for pasangan in pasangan_list:
        nf = _dapatkan_nilai_field(pasangan.field_dokumen, hasil_field)
        nilai_dok = nf.nilai_normalisasi if nf else ""

        if not nilai_dok:
            # Nilai dokumen tidak ada - tidak bisa cocok
            if pasangan.peran == PeranPasangan.WAJIB:
                # Semua baris gagal wajib ini - ditangani setelah tahu kandidat
                pass
            continue

        opsi = pasangan.normalisasi
        nilai_dok_norm = normalisasi_teks(nilai_dok, opsi) if nf else ""

        # Dapatkan kandidat berdasarkan mode
        kandidat_baris: set[str] = set()

        if pasangan.mode in (ModeCocok.PERSIS, ModeCocok.PERSIS_NORMALISASI):
            if pasangan.mode == ModeCocok.PERSIS:
                normalisasi_teks(nf.nilai_mentah if nf else "", OpsiNormalisasi())
                # Untuk PERSIS, cari dengan normalisasi minimal
                kandidat_baris = indeks.cari_persis(pasangan.kolom_rekap, nilai_dok_norm)
            else:
                kandidat_baris = indeks.cari_persis(pasangan.kolom_rekap, nilai_dok_norm)

        elif pasangan.mode == ModeCocok.MIRIP:
            hasil_fuzzy = indeks.cari_fuzzy(
                pasangan.kolom_rekap,
                nilai_dok_norm,
                pasangan.ambang_mirip,
            )
            kandidat_baris = {bid for bid, _ in hasil_fuzzy}

        elif pasangan.mode == ModeCocok.MENGANDUNG:
            kandidat_baris = indeks.cari_mengandung(pasangan.kolom_rekap, nilai_dok_norm)

        elif pasangan.mode == ModeCocok.DIAWALI:
            kandidat_baris = indeks.cari_diawali(pasangan.kolom_rekap, nilai_dok_norm)

        elif pasangan.mode in (
            ModeCocok.NUMERIK,
            ModeCocok.TANGGAL_SAMA,
            ModeCocok.TANGGAL_DOKUMEN_LEBIH_KECIL,
            ModeCocok.TANGGAL_DOKUMEN_LEBIH_BESAR,
        ):
            # Untuk numerik/tanggal, perlu bandingkan satu per satu
            # (tidak bisa pakai hash langsung)
            for baris in tabel.baris:
                nilai_rek_mentah = baris.data.get(pasangan.kolom_rekap, "")
                hasil_pas = cocokkan_pasangan(
                    pasangan,
                    nf.nilai_mentah if nf else "",
                    nilai_rek_mentah,
                    nf.meragukan if nf else False,
                )
                if hasil_pas.cocok:
                    kandidat_baris.add(baris.id)

        # Tambah skor untuk tiap kandidat yang cocok
        for bid in kandidat_baris:
            skor_baris[bid] += 1
            if bid not in skor_bobot:
                skor_bobot[bid] = 0.0
            skor_bobot[bid] += pasangan.bobot

        # Tandai baris yang gagal di pasangan WAJIB
        if pasangan.peran == PeranPasangan.WAJIB:
            # Semua baris yang TIDAK di kandidat_baris gagal di pasangan ini
            # Ini ditangani di langkah filter
            semua_baris_id = {b.id for b in tabel.baris}
            gagal_baris_wajib = semua_baris_id - kandidat_baris
            gagal_wajib.update(gagal_baris_wajib)

    # ── Langkah 2: Filter baris yang memenuhi kriteria ───────────────────────
    k = skema.k_minimum
    n_total = len(pasangan_list)

    # Ambil baris yang memenuhi K dan tidak gagal wajib
    kandidat_lolos: list[tuple[str, int, float]] = []  # (id, skor, bobot)
    for bid, skor in skor_baris.most_common():
        if bid in gagal_wajib:
            continue
        if skema.gunakan_bobot:
            if skor_bobot.get(bid, 0.0) >= k:
                kandidat_lolos.append((bid, skor, skor_bobot.get(bid, 0.0)))
        else:
            if skor >= k:
                kandidat_lolos.append((bid, skor, skor_bobot.get(bid, 0.0)))

    # Urutkan deterministik: skor turun, lalu id naik (untuk stabilitas)
    kandidat_lolos.sort(key=lambda x: (-x[1], x[0]))

    # ── Langkah 3: Evaluasi kandidat ─────────────────────────────────────────

    if not kandidat_lolos:
        # Tidak ada yang lolos K - cari "hampir cocok" untuk petunjuk
        kandidat_hampir = _cari_hampir_cocok(skor_baris, gagal_wajib, k, tabel)
        return HasilSkema(
            skema_id=skema.id,
            skema_nama=skema.nama,
            baris_rekap_id=None,
            baris_rekap_nomor=None,
            skor_total=n_total,
            status=StatusValidasi.TIDAK_VALID,
            alasan=f"Tidak ada baris yang memenuhi minimal {k} pasangan cocok.",
            kandidat_lain=kandidat_hampir,
        )

    baris_terbaik_id, skor_terbaik, _bobot_terbaik = kandidat_lolos[0]

    # Cek ambiguitas: apakah ada peringkat kedua yang terlalu dekat?
    if len(kandidat_lolos) > 1:
        _, skor_kedua, _ = kandidat_lolos[1]
        selisih = skor_terbaik - skor_kedua
        if selisih < skema.min_selisih_skor:
            # Ambigu - tampilkan semua kandidat skor tertinggi
            kandidat_skor_sama = [(bid, s) for bid, s, _ in kandidat_lolos if s >= skor_kedua]
            return _buat_hasil_ambigu(
                skema,
                kandidat_skor_sama,
                skor_terbaik,
                n_total,
                indeks,
                hasil_field,
            )

    # Tepat satu baris terbaik
    baris_terbaik = indeks.dapatkan_baris(baris_terbaik_id)
    if baris_terbaik is None:
        return HasilSkema(
            skema_id=skema.id,
            skema_nama=skema.nama,
            baris_rekap_id=None,
            baris_rekap_nomor=None,
            status=StatusValidasi.TIDAK_VALID,
            alasan="Baris terbaik tidak ditemukan (bug internal).",
        )

    # Hitung detail hasil tiap pasangan untuk baris terbaik
    hasil_pasangan = _hitung_detail_pasangan(skema, hasil_field, baris_terbaik)
    n_cocok = sum(1 for hp in hasil_pasangan if hp.cocok)

    # Tentukan status akhir
    status, alasan = _tentukan_status(skema, hasil_pasangan, n_cocok, n_total)

    kandidat_lain_tuple = tuple((bid, s) for bid, s, _ in kandidat_lolos[1:6])

    return HasilSkema(
        skema_id=skema.id,
        skema_nama=skema.nama,
        baris_rekap_id=baris_terbaik_id,
        baris_rekap_nomor=baris_terbaik.nomor_baris_asli,
        file_rekap=baris_terbaik.sumber_file,
        sheet_rekap=baris_terbaik.sumber_sheet,
        skor=n_cocok,
        skor_total=n_total,
        pasangan_hasil=tuple(hasil_pasangan),
        kandidat_lain=kandidat_lain_tuple,
        status=status,
        alasan=alasan,
    )


def _hitung_detail_pasangan(
    skema: SkemaPencocokan,
    hasil_field: tuple[NilaiField, ...],
    baris: BarisRekap,
) -> list[HasilPasangan]:
    """Hitung detail cocok/tidak untuk tiap pasangan terhadap baris tertentu."""
    hasil: list[HasilPasangan] = []
    for pasangan in skema.pasangan:
        nf = _dapatkan_nilai_field(pasangan.field_dokumen, hasil_field)
        nilai_dok = nf.nilai_mentah if nf else ""
        nilai_rek = baris.data.get(pasangan.kolom_rekap, "")
        meragukan = nf.meragukan if nf else False
        hp = cocokkan_pasangan(pasangan, nilai_dok, nilai_rek, meragukan)
        hasil.append(hp)
    return hasil


def _tentukan_status(
    skema: SkemaPencocokan,
    hasil_pasangan: list[HasilPasangan],
    n_cocok: int,
    n_total: int,
) -> tuple[StatusValidasi, str]:
    """Tentukan status akhir berdasarkan hasil pasangan."""
    # Cek pasangan WAJIB
    for hp in hasil_pasangan:
        # Temukan pasangan yang perannya WAJIB
        for pas in skema.pasangan:
            if pas.id == hp.pasangan_id and pas.peran == PeranPasangan.WAJIB:
                if not hp.cocok:
                    return (
                        StatusValidasi.TIDAK_VALID,
                        f"Pasangan WAJIB tidak cocok: [{pas.field_dokumen}] vs [{pas.kolom_rekap}]",
                    )

    # Cek K dari N
    k = skema.k_minimum
    ada_yang_meragukan = any(hp.meragukan for hp in hasil_pasangan)

    if n_cocok < k:
        return (
            StatusValidasi.TIDAK_VALID,
            f"Hanya {n_cocok} dari {n_total} pasangan cocok (minimal {k}).",
        )

    # K terpenuhi
    ada_tidak_cocok = any(not hp.cocok for hp in hasil_pasangan)

    if ada_tidak_cocok:
        perlakuan = skema.jika_ada_tidak_cocok
        if perlakuan == JikaAdaTidakCocok.TIDAK_VALID:
            return (
                StatusValidasi.TIDAK_VALID,
                f"Ada pasangan tidak cocok (skor {n_cocok}/{n_total}, K={k}).",
            )
        elif perlakuan == JikaAdaTidakCocok.PERLU_DICEK:
            return (
                StatusValidasi.PERLU_DICEK,
                f"Ada pasangan tidak cocok, perlu dicek manual (skor {n_cocok}/{n_total}).",
            )
        # VALID_CATATAN - tetap valid, catatan ada di detail pasangan

    if ada_yang_meragukan:
        return (
            StatusValidasi.PERLU_DICEK,
            "Keputusan bergantung pada data OCR yang meragukan (confidence rendah).",
        )

    return (
        StatusValidasi.VALID,
        f"Cocok {n_cocok} dari {n_total} pasangan (K={k}).",
    )


def _buat_hasil_ambigu(
    skema: SkemaPencocokan,
    kandidat: list[tuple[str, int]],
    skor: int,
    n_total: int,
    indeks: IndeksRekap,
    hasil_field: tuple[NilaiField, ...],
) -> HasilSkema:
    """Buat HasilSkema ketika ada dua atau lebih kandidat dengan skor sama."""
    info_kandidat = []
    for bid, s in kandidat[:5]:
        baris = indeks.dapatkan_baris(bid)
        if baris:
            info_kandidat.append(f"Baris {baris.nomor_baris_asli} (skor {s})")

    return HasilSkema(
        skema_id=skema.id,
        skema_nama=skema.nama,
        baris_rekap_id=None,
        baris_rekap_nomor=None,
        skor=skor,
        skor_total=n_total,
        kandidat_lain=tuple(kandidat[:5]),
        status=StatusValidasi.PERLU_DICEK,
        alasan=f"Ambigu: {len(kandidat)} baris dengan skor sama ({skor}/{n_total}). "
        f"Kandidat: {'; '.join(info_kandidat)}",
    )


def _cari_hampir_cocok(
    skor_baris: Counter[str],
    gagal_wajib: set[str],
    k: int,
    tabel: Any,
) -> tuple[tuple[str, int], ...]:
    """Cari baris hampir cocok (skor K-1 atau K-2) untuk petunjuk."""
    ambang_hampir = max(1, k - FUZZY_NEAR_MISS_DECREMENT)
    kandidat: list[tuple[str, int]] = []

    for bid, skor in skor_baris.most_common(10):
        if bid in gagal_wajib:
            continue
        if ambang_hampir <= skor < k:
            kandidat.append((bid, skor))

    return tuple(kandidat)


def cocokkan_dokumen(
    hasil_field: tuple[NilaiField, ...],
    skema_list: tuple[SkemaPencocokan, ...],
    indeks: IndeksRekap,
) -> tuple[HasilSkema, ...]:
    """
    Cocokkan satu dokumen dengan semua skema secara berurutan.

    Skema dicoba berurutan berdasarkan prioritas. Jika skema pertama
    menghasilkan VALID atau PERLU_DICEK, skema berikutnya tidak dijalankan.

    Args:
        hasil_field: Field yang diekstrak dari dokumen.
        skema_list: Daftar skema berurutan prioritas.
        indeks: Indeks terbalik tabel rekapan.

    Returns:
        Tuple semua HasilSkema yang dicoba (untuk jejak lengkap).
    """
    semua_hasil: list[HasilSkema] = []

    for skema in skema_list:
        if not skema.aktif:
            continue

        hasil = terapkan_skema(skema, hasil_field, indeks)
        semua_hasil.append(hasil)

        # Hentikan jika sudah ditemukan (tidak perlu coba skema berikutnya)
        if hasil.status in (StatusValidasi.VALID, StatusValidasi.PERLU_DICEK):
            break

    return tuple(semua_hasil)


def uji_tabrakan(
    skema: SkemaPencocokan,
    indeks: IndeksRekap,
) -> dict[str, Any]:
    """
    Uji tabrakan: untuk setiap baris rekapan, simulasikan sebagai dokumen
    dan hitung berapa baris LAIN yang ikut lolos ambang K.

    Returns:
        Dict berisi: total_baris, baris_dengan_kembaran, persen_tabrakan,
                     contoh_pasangan_kembar, saran
    """
    tabel = indeks.tabel
    total = len(tabel.baris)
    tabrakan: int = 0
    contoh_kembar: list[dict[str, Any]] = []

    for baris_target in tabel.baris:
        # Buat NilaiField palsu dari baris ini
        field_palsu: list[NilaiField] = []
        for pasangan in skema.pasangan:
            from validator_dokumen.core.models import SumberData

            nilai_mentah = baris_target.data.get(pasangan.kolom_rekap, "")
            opsi = pasangan.normalisasi
            nilai_norm = normalisasi_teks(nilai_mentah, opsi)
            nf = NilaiField(
                nama_field=pasangan.field_dokumen,
                nilai_mentah=nilai_mentah,
                nilai_normalisasi=nilai_norm,
                halaman=1,
                kotak=None,
                sumber=SumberData.TEKS,
                confidence=100.0,
                kandidat_lain=(),
            )
            field_palsu.append(nf)

        hasil = terapkan_skema(skema, tuple(field_palsu), indeks)

        # Hitung berapa baris LAIN yang lolos (bukan baris ini sendiri)
        if hasil.baris_rekap_id and hasil.baris_rekap_id != baris_target.id:
            tabrakan += 1
            if len(contoh_kembar) < 5:
                baris_kembar = indeks.dapatkan_baris(hasil.baris_rekap_id)
                contoh_kembar.append(
                    {
                        "baris_asal": baris_target.nomor_baris_asli,
                        "baris_kembar": baris_kembar.nomor_baris_asli if baris_kembar else "?",
                        "skor": hasil.skor,
                    }
                )
        elif hasil.status == StatusValidasi.PERLU_DICEK and hasil.kandidat_lain:
            tabrakan += 1

    persen = (tabrakan / total * 100) if total > 0 else 0.0

    # Saran
    if tabrakan == 0:
        saran = "Kombinasi kunci sudah kuat, tidak ada tabrakan."
    elif persen < 1.0:
        saran = f"Hanya {tabrakan} baris bermasalah (<1%). Pertimbangkan menambah pasangan WAJIB."
    else:
        saran = (
            f"{tabrakan} baris ({persen:.1f}%) berpotensi tertukar. "
            f"Naikkan K atau tambah kolom identifikasi sebagai WAJIB."
        )

    return {
        "total_baris": total,
        "baris_dengan_kembaran": tabrakan,
        "persen_tabrakan": round(persen, 2),
        "contoh_pasangan_kembar": contoh_kembar,
        "saran": saran,
    }
