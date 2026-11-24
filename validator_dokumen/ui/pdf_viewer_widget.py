"""
ui/pdf_viewer_widget.py - Penampil gambar halaman PDF dengan zoom dan sorotan bounding box.

Memuat gambar halaman secara lazy dengan LRU cache untuk hemat memori.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from validator_dokumen.core.constants import PAGE_IMAGE_CACHE_SIZE
from validator_dokumen.core.pdf_reader import render_halaman_preview
from validator_dokumen.ui.theme import COLORS


class _LruImageCache:
    """Cache sederhana LRU untuk QPixmap halaman PDF."""

    def __init__(self, capacity: int = PAGE_IMAGE_CACHE_SIZE) -> None:
        self._capacity = capacity
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()

    def get(self, key: str) -> QPixmap | None:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, pixmap: QPixmap) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = pixmap
        if len(self._cache) > self._capacity:
            self._cache.popitem(last=False)


_GLOBAL_IMAGE_CACHE = _LruImageCache()


class _PdfCanvas(QWidget):
    """Kanvas gambar PDF yang menggambar pixmap dan kotak sorot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._highlight_box: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1)
        self._scale: float = 1.0

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self._update_size()
        self.update()

    def set_highlight(self, box: tuple[float, float, float, float] | None) -> None:
        self._highlight_box = box
        self.update()

    def set_zoom(self, scale: float) -> None:
        self._scale = max(0.2, min(scale, 3.0))
        self._update_size()
        self.update()

    def zoom_level(self) -> float:
        return self._scale

    def _update_size(self) -> None:
        if self._pixmap:
            w = int(self._pixmap.width() * self._scale)
            h = int(self._pixmap.height() * self._scale)
            self.setFixedSize(w, h)
        else:
            self.setFixedSize(400, 500)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._pixmap:
            painter.fillRect(self.rect(), QColor(COLORS.bg_app))
            painter.setPen(QColor(COLORS.text_muted))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Pratinjau dokumen tidak tersedia"
            )
            return

        # Gambar pixmap
        scaled_pixmap = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, scaled_pixmap)

        # Gambar kotak sorot jika ada
        if self._highlight_box and self._pixmap.width() > 0:
            x0, y0, x1, y1 = self._highlight_box
            # Rasio terhadap ukuran asli
            rx = self.width() / self._pixmap.width()
            ry = self.height() / self._pixmap.height()

            rect_highlight = QRectF(x0 * rx, y0 * ry, (x1 - x0) * rx, (y1 - y0) * ry)

            pen = QPen(QColor("#2563EB"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(37, 99, 235, 40))  # Biru transparan
            painter.drawRect(rect_highlight)


class PdfViewerWidget(QWidget):
    """
    Widget lengkap penampil PDF: kontrol zoom, scroll area, dan lazy image loading.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_path: Path | None = None
        self._current_page: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar atas
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        toolbar.setSpacing(8)

        self._lbl_page = QLabel("Halaman 1")
        self._lbl_page.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {COLORS.text_secondary};"
        )
        toolbar.addWidget(self._lbl_page)
        toolbar.addStretch()

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedSize(28, 28)
        btn_zoom_out.clicked.connect(self._zoom_out)
        toolbar.addWidget(btn_zoom_out)

        self._lbl_zoom = QLabel("100%")
        self._lbl_zoom.setFixedWidth(45)
        self._lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_zoom.setStyleSheet(f"font-size: 11px; color: {COLORS.text_secondary};")
        toolbar.addWidget(self._lbl_zoom)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(28, 28)
        btn_zoom_in.clicked.connect(self._zoom_in)
        toolbar.addWidget(btn_zoom_in)

        layout.addLayout(toolbar)

        # Scroll Area
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setStyleSheet(
            f"background-color: {COLORS.bg_app}; border: 1px solid {COLORS.border}; border-radius: 6px;"
        )

        self._canvas = _PdfCanvas()
        self._scroll_area.setWidget(self._canvas)
        layout.addWidget(self._scroll_area, stretch=1)

    def load_document(
        self,
        pdf_path: Path | str,
        page_num: int = 0,
        highlight_box: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Muat dan tampilkan halaman PDF dengan kotak sorot opsional."""
        path = Path(pdf_path)
        self._current_path = path
        self._current_page = page_num
        self._lbl_page.setText(f"Halaman {page_num + 1}")

        cache_key = f"{path}:{page_num}"
        cached = _GLOBAL_IMAGE_CACHE.get(cache_key)

        if cached:
            self._canvas.set_pixmap(cached)
        else:
            pil_img = render_halaman_preview(path, page_num, dpi=130)
            if pil_img:
                from PIL.ImageQt import ImageQt  # type: ignore[import-untyped]

                qimg = ImageQt(pil_img)
                pixmap = QPixmap.fromImage(qimg)
                _GLOBAL_IMAGE_CACHE.put(cache_key, pixmap)
                self._canvas.set_pixmap(pixmap)
            else:
                self._canvas.set_pixmap(None)

        self._canvas.set_highlight(highlight_box)

    def load_pdf(self, pdf_path: Path | str, page_num: int = 0) -> None:
        """Alias untuk load_document."""
        self.load_document(pdf_path, page_num=page_num)

    def _zoom_in(self) -> None:
        curr = self._canvas.zoom_level()
        self._canvas.set_zoom(curr + 0.15)
        self._lbl_zoom.setText(f"{int(self._canvas.zoom_level() * 100)}%")

    def _zoom_out(self) -> None:
        curr = self._canvas.zoom_level()
        self._canvas.set_zoom(curr - 0.15)
        self._lbl_zoom.setText(f"{int(self._canvas.zoom_level() * 100)}%")
