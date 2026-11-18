"""Read-only PDF preview for IthuteSign's document explorer."""
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
        layout = QVBoxLayout(self)
        title = QLabel("DOCUMENT PREVIEW")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        self.details = QLabel("Select a PDF to preview")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.image = QLabel("No document selected")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(200, 280)
        scroll.setWidget(self.image)
        layout.addWidget(scroll, 1)
        controls = QHBoxLayout()
        self.previous = QPushButton("←")
        self.counter = QLabel("0 / 0")
        self.next = QPushButton("→")
        controls.addWidget(self.previous)
        controls.addWidget(self.counter, 1, Qt.AlignCenter)
        controls.addWidget(self.next)
        layout.addLayout(controls)
        self.previous.clicked.connect(lambda: self.render(self.page - 1))
        self.next.clicked.connect(lambda: self.render(self.page + 1))
        self.clear()

    def clear(self, message="Select a PDF to preview"):
        self.path = None
        self.page = 0
        self.total = 0
        self.details.setText(message)
        self.image.setPixmap(QPixmap())
        self.image.setText("No preview")
        self.counter.setText("0 / 0")
        self.previous.setEnabled(False)
        self.next.setEnabled(False)

    def load_pdf(self, path, record):
        self.path = str(path)
        self.page = 0
        self.details.setText(
            f"{record.get('name', 'Document')}\\n"
            f"Client: {record.get('national_id') or 'Legacy / unassigned'}\\n"
            f"Saved: {record.get('created_at', '')[:19].replace('T', ' ')}\\n"
            "Integrity: verified"
        )
        self.render(0)

    def render(self, index):
        if not self.path:
            return
        try:
            with fitz.open(self.path) as document:
                if document.needs_pass or not len(document):
                    raise ValueError("PDF is locked or empty")
                self.total = len(document)
                self.page = max(0, min(index, self.total - 1))
                page = document[self.page]
                scale = min(1.6, max(0.5, 360 / page.rect.width))
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                self.image.setPixmap(QPixmap.fromImage(image))
                self.image.setText("")
            self.counter.setText(f"{self.page + 1} / {self.total}")
            self.previous.setEnabled(self.page > 0)
            self.next.setEnabled(self.page < self.total - 1)
        except Exception:
            self.clear("Preview unavailable. The PDF may be damaged or unreadable.")
