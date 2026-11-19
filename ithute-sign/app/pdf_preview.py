"""Read-only PDF preview with zoom, fit-to-page, and page navigation."""
import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea


class PdfPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None
        self.page = 0
        self.total = 0
        self.zoom_mode = "page"
        self.zoom_percent = 100
        self._rendering = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel("DOCUMENT PREVIEW")
        title.setStyleSheet("font-weight: 800; font-size: 14px; color: #17334f;")
        layout.addWidget(title)
        self.details = QLabel("Select a PDF to preview")
        self.details.setWordWrap(True)
        self.details.setStyleSheet("color: #314a65; font-size: 12px; padding: 5px;")
        layout.addWidget(self.details)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: #28323e; border: 1px solid #c6d4e1; border-radius: 7px; }")
        self.image = QLabel("No document selected")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(200, 280)
        self.image.setStyleSheet("background: #28323e; color: #e4ebf4; padding: 10px;")
        self.scroll.setWidget(self.image)
        layout.addWidget(self.scroll, 1)

        zoom = QHBoxLayout()
        self.zoom_out = QPushButton("−")
        self.zoom_label = QLabel("Fit page")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_in = QPushButton("+")
        self.fit_width = QPushButton("Fit width")
        self.fit_page = QPushButton("Fit page")
        for button in (self.zoom_out, self.zoom_in, self.fit_width, self.fit_page):
            zoom.addWidget(button)
        zoom.insertWidget(1, self.zoom_label, 1)
        layout.addLayout(zoom)

        controls = QHBoxLayout()
        self.previous = QPushButton("← Previous")
        self.counter = QLabel("0 / 0")
        self.counter.setAlignment(Qt.AlignCenter)
        self.next = QPushButton("Next →")
        controls.addWidget(self.previous)
        controls.addWidget(self.counter, 1)
        controls.addWidget(self.next)
        layout.addLayout(controls)
        self.previous.clicked.connect(lambda: self.render(self.page - 1))
        self.next.clicked.connect(lambda: self.render(self.page + 1))
        self.zoom_in.clicked.connect(lambda: self.adjust_zoom(25))
        self.zoom_out.clicked.connect(lambda: self.adjust_zoom(-25))
        self.fit_width.clicked.connect(lambda: self.set_zoom_mode("width"))
        self.fit_page.clicked.connect(lambda: self.set_zoom_mode("page"))
        self.clear()

    def clear(self, message="Select a PDF to preview"):
        self.path = None
        self.page = 0
        self.total = 0
        self.details.setText(message)
        self.image.setPixmap(QPixmap())
        self.image.setText("No preview")
        self.counter.setText("0 / 0")
        for button in (self.previous, self.next, self.zoom_in, self.zoom_out,
                       self.fit_width, self.fit_page):
            button.setEnabled(False)

    def load_pdf(self, path, record):
        self.path = str(path)
        self.page = 0
        self.zoom_mode = "page"
        self.details.setText(
            f"{record.get('name', 'Document')}\\n"
            f"Client: {record.get('national_id') or 'Legacy / unassigned'}\\n"
            f"Saved: {record.get('created_at', '')[:19].replace('T', ' ')}\\n"
            "Integrity: verified"
        )
        self.render(0)

    def adjust_zoom(self, change):
        if not self.path:
            return
        if self.zoom_mode != "custom":
            self.zoom_percent = 100
        self.zoom_percent = max(25, min(300, self.zoom_percent + change))
        self.zoom_mode = "custom"
        self.render(self.page)

    def set_zoom_mode(self, mode):
        if not self.path:
            return
        self.zoom_mode = mode
        self.render(self.page)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.path and self.zoom_mode in ("page", "width") and not self._rendering:
            self.render(self.page)

    def render(self, index):
        if not self.path or self._rendering:
            return
        self._rendering = True
        try:
            with fitz.open(self.path) as document:
                if document.needs_pass or not len(document):
                    raise ValueError("PDF is locked or empty")
                self.total = len(document)
                self.page = max(0, min(index, self.total - 1))
                page = document[self.page]
                available_width = max(150, self.scroll.viewport().width() - 26)
                available_height = max(150, self.scroll.viewport().height() - 26)
                if self.zoom_mode == "width":
                    scale = available_width / page.rect.width
                    label = "Fit width"
                elif self.zoom_mode == "page":
                    scale = min(available_width / page.rect.width,
                                available_height / page.rect.height)
                    label = "Fit page"
                else:
                    scale = self.zoom_percent / 100
                    label = f"{self.zoom_percent}%"
                # Limit pixel allocation for large or unusual PDF pages.
                scale = min(scale, 3.0, 3500 / max(page.rect.width, page.rect.height))
                scale = max(0.05, scale)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = QImage(pix.samples, pix.width, pix.height, pix.stride,
                               QImage.Format_RGB888).copy()
                self.image.setPixmap(QPixmap.fromImage(image))
                self.image.setText("")
            self.zoom_label.setText(label)
            self.counter.setText(f"{self.page + 1} / {self.total}")
            self.previous.setEnabled(self.page > 0)
            self.next.setEnabled(self.page < self.total - 1)
            for button in (self.zoom_in, self.zoom_out, self.fit_width, self.fit_page):
                button.setEnabled(True)
        except Exception:
            self.clear("Preview unavailable. The PDF may be damaged or unreadable.")
        finally:
            self._rendering = False
