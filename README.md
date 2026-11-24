# Validator Dokumen

Aplikasi desktop Windows modern dan tangguh untuk melakukan verifikasi, ekstraksi, dan validasi dokumen perizinan (PDF teks atau hasil pemindaian/OCR) terhadap tabel rekapan acuan (Excel `.xlsx` atau PDF tabel) secara **sepenuhnya dinamis** tanpa ada nama kolom atau field yang dikodekan permanen (hardcoded).

---

## 🌟 Fitur Utama

1. **Pemetaan Pencocokan Sepenuhnya Dinamis (Zero Hardcoding)**:
   - Kolom rekapan dibaca secara otomatis dari header Excel/PDF.
   - Field dokumen izin diekstraksi berdasarkan definisi fleksibel (label, regex, posisi/koordinat, atau tabel).
   - Pengguna bebas menyusun pasangan pemetaan, mode, dan opsi normalisasi langsung dari antarmuka visual.

2. **Mesin Pencocokan Multi-Skema & Ambang K dari N**:
   - Mendukung banyak skema berurutan prioritas.
   - Setiap skema mendukung kombinasi pasangan **Kunci** (pencarian baris berindeks cepat) dan pasangan **Pembanding** (ambang $K$ dari $N$ pasangan harus cocok).
   - Berbagai mode pencocokan: *Persis*, *Persis setelah normalisasi*, *Toleran (Fuzzy rapidfuzz)*, *Mengandung*, *Diawali dengan*, *Numerik (toleransi selisih)*, dan *Tanggal (sama persis / $\le$ / $\ge$)*.

3. **Pembersihan & Normalisasi Teks Otomatis**:
   - Mengabaikan huruf besar/kecil, spasi ganda, tanda baca, awalan/akhiran badan usaha (PT, CV, UD, PD, Tbk), serta nol di depan angka.
   - Koreksi otomatis karakter keliru akibat OCR (seperti huruf `O` dengan angka `0`, `I` dengan `1`, `S` dengan `5`, dsb.).

4. **Mesin Ekstraksi & OCR Cerdas**:
   - Mendeteksi dokumen teks asli vs dokumen gambar/pindaian secara otomatis.
   - Pipeline pra-pemrosesan citra adaptif: render 300 DPI, konversi grayscale, threshold adaptif Otsu, deskewing, dan denoise sebelum Tesseract OCR (bahasa `ind+eng`).
   - Caching disk hasil OCR cerdas berbasis hash SHA-256 untuk kecepatan pengujian ulang seketika.

5. **Aturan Kondisional Visual (JIKA-MAKA)**:
   - Aturan logika kondisional: `JIKA [field/kolom] [operator] [nilai] MAKA [aksi]`.

6. **Keterjelasan & Jejak Keputusan (Decision Trace)**:
   - Setiap berkas yang diperiksa membawa rantai keputusan transparan: nilai mentah $\rightarrow$ nilai ternormalisasi $\rightarrow$ aturan/mode $\rightarrow$ hasil evaluasi $\rightarrow$ alasan.
   - Panel visual interaktif *"Kenapa hasilnya begini?"* untuk memudahkan audit.

7. **Kinerja Bulk Skala Besar**:
   - Pemrosesan paralel multi-core (`ProcessPoolExecutor`) dengan isolasi penuh: kerusakan satu dokumen tidak akan menghentikan ribuan dokumen lainnya.
   - Manajemen memori terkontrol dengan rendering PDF lazy dan batas LRU.
   - Penulisan berkas keluaran secara atomik (temporary file $\rightarrow$ rename) agar bebas korupsi data saat proses terputus.

8. **Laporan Audit Lengkap**:
   - Laporan Excel hasil validasi (`laporan_validasi.xlsx`) berformat rapi dengan pewarnaan status.
   - Laporan rekapan tidak terpakai (`rekapan_tidak_terpakai.xlsx`) untuk mendeteksi data acuan yang tidak memiliki dokumen pendukung.
   - Catatan audit teks (`audit_log.txt`) dengan metadata reproduksi (hash profil, hash rekapan, waktu proses).

---

## 🖥️ Antarmuka Pengguna (UI)

Aplikasi dibangun menggunakan **PySide6** dengan desain modern berbasis tema Segoe UI:
- **Layar Validasi**: Pemilihan profil aktif, penentuan file rekapan, pemilihan folder dokumen PDF target (bulk / single file), opsi lanjutan OCR, serta visualisasi progres pemrosesan real-time.
- **Layar Hasil**: Kartu statistik ringkasan (Valid, Tidak Valid, Perlu Dicek, Tidak Bisa Dibaca), filter status instan, pencarian nama berkas, tabel data Model/View berperforma tinggi, inspektur detail pasangan diff (Dokumen vs Rekapan), pratinjau visual halaman PDF, jejak keputusan lengkap, serta opsi pengubahan status manual disertai alasan audit.
- **Layar Siapkan Profil (Wizard 5 Langkah)**:
  1. *Pilih Rekapan*: Muat file Excel, pilih sheet, tentukan baris header, pratinjau tabel rekapan, dan analisis kualitas kolom.
  2. *Contoh & Field*: Muat contoh PDF, viewer pratinjau interaktif dengan zoom dan seleksi kotak koordinat, definisikan field (label/regex/koordinat), dan uji ekstraksi langsung.
  3. *Pencocokan*: Susun skema pencocokan, tambahkan pasangan kolom $\leftrightarrow$ field, tentukan peran Kunci/Pembanding, pilih mode dan normalisasi, saran pemetaan otomatis, analisis tabrakan kunci, serta penentuan ambang $K$ dari $N$.
  4. *Aturan Tambahan*: Validasi nilai field (wajib terisi, format regex, batas angka/tanggal) dan editor aturan visual JIKA-MAKA.
  5. *Uji & Simpan*: Uji coba pencocokan pada contoh dokumen secara langsung, evaluasi tabel diff, lengkapi metadata profil, lalu simpan ke berkas profil JSON.

---

## 📁 Struktur Proyek

```text
dokumen-validator/
├── main.py                     # Entry point aplikasi desktop GUI (PySide6)
├── cli.py                      # Antarmuka CLI untuk validasi otomatis/headless
├── check.bat                   # Skrip otomatis: Ruff (lint & format), Mypy, & Pytest
├── build.bat                   # Skrip bundling PyInstaller executable Windows
├── pyproject.toml              # Konfigurasi Ruff, Mypy, dan Pytest
├── requirements.txt            # Dependensi Python ter-pin
├── validator_dokumen/
│   ├── core/                   # Logika bisnis murni (bebas dependensi PySide6)
│   │   ├── constants.py        # Konstanta baku, versi, ambang OCR & fuzzy
│   │   ├── models.py           # Model data (dataclass frozen) & Enum status
│   │   ├── profile_schema.py   # Skema Pydantic profil & migrasi versi
│   │   ├── excel_reader.py     # Pembaca Excel (semua sel string teks)
│   │   ├── pdf_reader.py       # Pembaca PDF teks & tabel via PyMuPDF/pdfplumber
│   │   ├── ocr_engine.py       # Mesin OCR 300 DPI, OpenCV, & Tesseract
│   │   ├── normalizer.py       # Fungsi normalisasi teks, badan usaha, OCR fix
│   │   ├── field_extractor.py  # Ekstraktor field dokumen (label/regex/kotak)
│   │   ├── recap_table.py      # Pengelola tabel acuan & indeks kunci hash
│   │   ├── matcher.py          # Mesin pencocokan K dari N & multi-skema
│   │   ├── rule_engine.py      # Mesin aturan field & logika JIKA-MAKA
│   │   ├── decision_trace.py   # Perekam jejak keputusan deterministik
│   │   ├── output_writer.py    # Pemilah folder & generator laporan Excel/log
│   │   └── audit_log.py        # Generator ringkasan log audit
│   ├── services/               # Lapisan orkestrasi perantara UI/CLI ke Core
│   │   ├── validation_service.py # Orkestrasi validasi single file & bulk paralel
│   │   ├── profile_service.py    # Manajemen CRUD profil, ekspor/impor JSON
│   │   └── recap_service.py      # Muat rekapan acuan & analisis kolom
│   ├── workers/                # QThread / Worker asinkron untuk operasi berat
│   │   └── validation_worker.py  # Worker validasi dengan sinyal progres halus
│   ├── ui/                     # Antarmuka Pengguna (PySide6)
│   │   ├── main_window.py      # Jendela utama, sidebar 200px, topbar
│   │   ├── validation_view.py  # Layar konfigurasi validasi & progres
│   │   ├── results_view.py     # Layar penjelajah hasil & master-detail diff
│   │   ├── profile_wizard.py   # Wizard stepper 5 langkah pembuatan profil
│   │   ├── theme.py            # Token warna, typography, & generator QSS
│   │   ├── widgets/            # Komponen UI modular (Card, Buttons, Banner, dll)
│   │   └── steps/              # Widget masing-masing langkah Step 1 - Step 5
│   └── utils/                  # Utilitas logger berputar & resource path
├── tools/
│   ├── buat_data_contoh.py     # Generator data simulasi (rekapan & aneka PDF)
│   └── screenshot.py           # Penangkap layar otomatis seluruh tampilan UI
├── tests/                      # Rangkaian pengujian otomatis
│   ├── golden/                 # Golden test pencocokan skenario nyata
│   ├── test_matcher.py         # Pengujian logika pencocokan & K dari N
│   ├── test_normalizer.py      # Pengujian fungsi normalisasi teks
│   ├── test_rule_engine.py     # Pengujian aturan tambahan & JIKA-MAKA
│   ├── test_readers_and_extractor.py # Pengujian reader Excel/PDF & extractor
│   ├── test_services.py        # Pengujian lapisan service & orkestrasi
│   ├── test_ui.py              # Pengujian komponen UI & Model/View
│   └── test_wizard.py          # Pengujian antarmuka ProfileWizard
└── docs/screens/               # Pratinjau tangkapan layar antarmuka aplikasi
```

---

## 🚀 Panduan Memulai

### 1. Prasyarat Sistem
- **Sistem Operasi**: Windows 10 atau Windows 11 (64-bit).
- **Python**: Versi 3.11.x (disarankan 3.11.5+).
- **Tesseract OCR**: Pastikan Tesseract OCR terinstal (misalnya di `C:\Program Files\Tesseract-OCR`) dan menyertakan data bahasa Indonesia (`ind.traineddata`) serta Inggris (`eng.traineddata`).

### 2. Instalasi Dependensi
Buka terminal PowerShell atau Command Prompt pada direktori proyek, lalu jalankan:
```bash
pip install -r requirements.txt
```

### 3. Menghasilkan Data Contoh Pengujian
Untuk membuat berkas rekapan contoh (`rekapan.xlsx`) dan aneka berkas PDF uji coba (PDF teks, PDF salah, PDF kedaluwarsa, PDF gambar/scan, PDF rusak, dan PDF duplikat), jalankan:
```bash
python tools/buat_data_contoh.py
```

---

## 💻 Penggunaan CLI (Command Line Interface)

Aplikasi dapat dijalankan secara langsung dari terminal tanpa antarmuka grafis:

### Validasi Satu File PDF:
```bash
python cli.py \
    --profil "contoh_data/profil_izin_usaha.json" \
    --rekap "tests/data/rekapan.xlsx" \
    --target "tests/data/pdf_benar.pdf" \
    --output "output_uji_cli"
```

### Validasi Folder Bulk Dokumen PDF:
```bash
python cli.py \
    --profil "contoh_data/profil_izin_usaha.json" \
    --rekap "tests/data/rekapan.xlsx" \
    --target "tests/data" \
    --output "output_uji_bulk" \
    --subfolder \
    --workers 4
```

---

## 🖥️ Menjalankan Aplikasi Desktop (GUI)

Cukup jalankan berkas `main.py`:
```bash
python main.py
```

### Alur Kerja di Aplikasi:
1. **Pilih / Buat Profil**: Di layar *Siapkan Profil*, ikuti 5 langkah untuk menentukan kolom acuan, field dokumen, mode pencocokan $K$ dari $N$, dan aturan tambahan.
2. **Jalankan Validasi**: Buka layar *Validasi*, pilih profil dan file rekapan, pilih folder target PDF, lalu klik tombol **MULAI VALIDASI**.
3. **Analisis Hasil**: Begitu selesai, layar *Hasil* otomatis terbuka menampilkan ringkasan visual, daftar berkas, diff data dokumen vs rekapan, dan pratinjau PDF.

---

## 🧪 Pengujian Otomatis & Standar Kualitas

Proyek ini menerapkan standar pengujian ketat dengan cakupan kode di atas 85%:
- **Linter & Formatter**: `ruff check` dan `ruff format --check`
- **Pengecekan Tipe**: `mypy --strict validator_dokumen/core validator_dokumen/services`
- **Unit & Integration Test**: `pytest tests/ --cov=validator_dokumen/core --cov=validator_dokumen/services --cov-fail-under=85`

Untuk menjalankan seluruh pengecekan kualitas sekaligus, cukup jalankan:
```cmd
.\check.bat
```

---

## 📦 Membangun Executable Windows (.exe)

Aplikasi dapat dibundel menjadi program Windows mandiri menggunakan PyInstaller:
```cmd
.\build.bat
```
Hasil kompilasi akan berada di folder `dist\ValidatorDokumen\ValidatorDokumen.exe`.

---

## 📄 Lisensi
Hak Cipta © 2026 Widy. Seluruh hak cipta dilindungi undang-undang.
