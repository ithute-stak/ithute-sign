"""IthuteSign offline Windows document-signing desktop.

Uses the official Wacom STU bridge when installed. Development mouse capture is
only available before creating the release-mode.flag production marker.
"""
import sys
import tempfile
import subprocess
import shutil
import uuid
from dataclasses import replace
from pathlib import Path
import fitz
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QScrollArea, QSpinBox,
    QDialog, QDialogButtonBox, QListWidget)
from document import to_pdf, sign_pdf_many, Placement
from device import probe_bridge, show_screen, validate_signature_png
from geometry import fit_rectangle

def root_folder():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def bridge_path():
    root = root_folder()
    for candidate in (root / "wacom-bridge" / "STUCapture.exe",
                      root / "wacom-bridge" / "bin" / "STUCapture.exe"):
        if candidate.is_file():
            return candidate
    return None

def release_mode():
    return (root_folder() / "release-mode.flag").exists()

class InkPad(QLabel):
    def __init__(self):
        super().__init__()
        self.setFixedSize(550, 185)
        self.image = QImage(550, 185, QImage.Format_ARGB32)
        self.image.fill(Qt.transparent)
        self.setStyleSheet("background:white;border:1px solid #c4d2df")
        self.previous = None
        self.strokes = 0
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.drawImage(0, 0, self.image)
        p.end()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.previous = event.position().toPoint()
    def mouseMoveEvent(self, event):
        if self.previous is None or not event.buttons() & Qt.LeftButton:
            return
        point = event.position().toPoint()
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#123a75"), 3, Qt.SolidLine,
                            Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(self.previous, point)
        painter.end()
        self.previous = point
        self.strokes += 1
        self.update()
    def mouseReleaseEvent(self, event):
        self.previous = None
    def clear(self):
        self.image.fill(Qt.transparent)
        self.strokes = 0
        self.update()
    def export(self, target):
        if self.strokes < 2:
            raise ValueError("Draw a signature first")
        # Save as transparent image; native STU bridge produces its own PNG.
        if not self.image.save(str(target), "PNG"):
            raise RuntimeError("Could not save signature PNG")

class CaptureDialog(QDialog):
    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folder = Path(folder)
        self.captured = None
        self.setWindowTitle("IthuteSign | Capture signature")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sign using the STU-540, then review before adding."))
        self.preview = QLabel("No STU signature captured")
        self.preview.setMinimumHeight(65)
        self.preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview)
        self.pad = InkPad()
        if release_mode():
            self.pad.hide()
        layout.addWidget(self.pad)
        row = QHBoxLayout()
        capture = QPushButton("Capture from STU-540")
        capture.clicked.connect(self.capture_stu)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        row.addWidget(capture)
        row.addWidget(clear)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def clear(self):
        self.captured = None
        self.pad.clear()
        self.preview.setPixmap(QPixmap())
        self.preview.setText("No STU signature captured")
    def capture_stu(self):
        bridge = bridge_path()
        status = probe_bridge(bridge)
        if not status.connected:
            QMessageBox.warning(self, "STU-540 unavailable", status.message)
            return
        target = self.folder / ("stu_" + uuid.uuid4().hex + ".png")
        try:
            result = subprocess.run([str(bridge), str(target)], timeout=180,
                                    text=True, capture_output=True)
            if result.returncode or not target.is_file():
                raise RuntimeError(result.stderr.strip() or "STU capture cancelled or failed")
            validate_signature_png(target)
            picture = QPixmap(str(target))
            if picture.isNull():
                raise RuntimeError("Invalid STU signature image")
            self.captured = str(target)
            self.pad.clear()
            self.preview.setPixmap(picture.scaled(520, 95, Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation))
        except Exception as exc:
            target.unlink(missing_ok=True)
            QMessageBox.warning(self, "STU capture error", str(exc))
    def export(self, target):
        if self.captured:
            shutil.copyfile(self.captured, target)
        elif release_mode():
            raise ValueError("Release mode requires a real STU-540 signature")
        else:
            self.pad.export(target)

class PageView(QLabel):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_index = None
        self.drag_offset = (0, 0)
        self.setCursor(Qt.CrossCursor)
        self.setStyleSheet("background:white;border:1px solid #bccddd")

    def mousePressEvent(self, event):
        if self.window.doc is None or event.button() != Qt.LeftButton:
            return
        x, y = event.position().x() / self.window.zoom, event.position().y() / self.window.zoom
        page = self.window.doc[self.window.page_index]
        if not (0 <= x < page.rect.width and 0 <= y < page.rect.height):
            return
        # Prefer moving an existing signature over creating a new placement.
        for i in range(len(self.window.signatures) - 1, -1, -1):
            item = self.window.signatures[i]
            if (item.page_index == self.window.page_index and
                item.x <= x <= item.x + item.width and
                item.y <= y <= item.y + item.height):
                self.drag_index = i
                self.drag_offset = (x - item.x, y - item.y)
                self.window.queue.setCurrentRow(i)
                self.setCursor(Qt.ClosedHandCursor)
                return
        self.window.position = (x, y)
        self.window.redraw()

    def mouseMoveEvent(self, event):
        if self.drag_index is None or self.window.doc is None:
            return
        if not (event.buttons() & Qt.LeftButton):
            return
        item = self.window.signatures[self.drag_index]
        page = self.window.doc[item.page_index]
        x = event.position().x() / self.window.zoom - self.drag_offset[0]
        y = event.position().y() / self.window.zoom - self.drag_offset[1]
        self.window.signatures[self.drag_index] = replace(
            item,
            x=max(0, min(x, page.rect.width - item.width)),
            y=max(0, min(y, page.rect.height - item.height)))
        self.window.redraw()

    def mouseReleaseEvent(self, event):
        self.drag_index = None
        self.setCursor(Qt.CrossCursor)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IthuteSign — Document signing")
        self.resize(1150, 830)
        self.temp = tempfile.TemporaryDirectory(prefix="ithutesign_")
        self.doc = None
        self.source = None
        self.preview_pdf = None
        self.page_index = 0
        self.zoom = 1.2
        self.position = None
        self.signatures = []
        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        heading = QLabel("ITHUTESIGN  |  Offline document signing")
        heading.setStyleSheet("font-size:19px;font-weight:700;color:#18355b;padding:10px")
        layout.addWidget(heading)
        controls = QHBoxLayout()
        for label, handler in (("Open PDF / Word", self.open_document),
                               ("Previous", self.previous), ("Next", self.next),
                               ("Add signature", self.add_signature),
                               ("Remove selected", self.remove_selected),
                               ("Device status", self.device_status),
                               ("Save signed PDF", self.save)):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            controls.addWidget(btn)
        layout.addLayout(controls)
        options = QHBoxLayout()
        options.addWidget(QLabel("Width (pt)"))
        self.width = QSpinBox()
        self.width.setRange(30, 400)
        self.width.setValue(160)
        options.addWidget(self.width)
        options.addWidget(QLabel("Height (pt)"))
        self.height = QSpinBox()
        self.height.setRange(15, 180)
        self.height.setValue(65)
        options.addWidget(self.height)
        options.addStretch()
        layout.addLayout(options)
        content = QHBoxLayout()
        self.scroll = QScrollArea()
        self.page = PageView(self)
        self.scroll.setWidget(self.page)
        content.addWidget(self.scroll, 4)
        side = QVBoxLayout()
        side.addWidget(QLabel("Queued signatures"))
        self.queue = QListWidget()
        side.addWidget(self.queue)
        content.addLayout(side, 1)
        layout.addLayout(content)
        self.status = QLabel("Connect STU-540. Open a document to begin. Drag existing signatures to reposition them.")
        layout.addWidget(self.status)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, self.welcome)
    def welcome(self):
        result = show_screen(bridge_path(), "welcome")
        self.status.setText("STU-540 welcome screen ready" if result.connected
                            else "STU-540: " + result.message)
    def device_status(self):
        result = probe_bridge(bridge_path())
        QMessageBox.information(self, "Device connection",
                                ("Connected" if result.connected else "Disconnected")
                                + "\n" + result.message)
    def open_document(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open document", "",
                                             "Documents (*.pdf *.docx *.doc)")
        if not path:
            return
        try:
            pdf = to_pdf(path, str(Path(self.temp.name) / (uuid.uuid4().hex + ".pdf")))
            new_doc = fitz.open(pdf)
            if not len(new_doc) or new_doc.needs_pass:
                raise ValueError("Document is empty or encrypted")
            if self.doc is not None:
                self.doc.close()
            self.doc = new_doc
            self.source = path
            self.preview_pdf = pdf
            self.page_index = 0
            self.position = None
            self.signatures.clear()
            self.queue.clear()
            self.redraw()
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
    def redraw(self):
        if self.doc is None:
            return
        page = self.doc[self.page_index]
        pixels = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom))
        image = QPixmap.fromImage(QImage(pixels.samples, pixels.width, pixels.height,
                                        pixels.stride, QImage.Format_RGB888).copy())
        painter = QPainter(image)
        for placement in self.signatures:
            if placement.page_index != self.page_index:
                continue
            x, y = round(placement.x * self.zoom), round(placement.y * self.zoom)
            w, h = round(placement.width * self.zoom), round(placement.height * self.zoom)
            pix = QPixmap(placement.signature_png)
            if not pix.isNull():
                rx, ry, rw, rh = fit_rectangle(x, y, w, h, pix.width(), pix.height())
                painter.drawPixmap(QRectF(rx, ry, rw, rh), pix, QRectF(pix.rect()))
            painter.setPen(QPen(QColor("#16935f"), 2))
            painter.drawRect(x, y, w, h)
        if self.position:
            painter.setPen(QPen(QColor("#117ac2"), 2, Qt.DashLine))
            painter.drawRect(round(self.position[0] * self.zoom),
                             round(self.position[1] * self.zoom),
                             round(self.width.value() * self.zoom),
                             round(self.height.value() * self.zoom))
        painter.end()
        self.page.setPixmap(image)
        self.page.setFixedSize(image.size())
        self.status.setText(f"{Path(self.source).name} | Page {self.page_index+1}/{len(self.doc)} | "
                            f"{len(self.signatures)} signature(s)")
    def previous(self):
        if self.doc is not None and self.page_index > 0:
            self.page_index -= 1
            self.position = None
            self.redraw()
    def next(self):
        if self.doc is not None and self.page_index + 1 < len(self.doc):
            self.page_index += 1
            self.position = None
            self.redraw()
    def add_signature(self):
        if self.doc is None or self.position is None:
            QMessageBox.warning(self, "Select position", "Open a document and click where to sign.")
            return
        x, y = self.position
        width, height = self.width.value(), self.height.value()
        page = self.doc[self.page_index]
        if x + width > page.rect.width or y + height > page.rect.height:
            QMessageBox.warning(self, "Position", "Signature must fit within the page.")
            return
        dialog = CaptureDialog(self.temp.name, self)
        if dialog.exec() != QDialog.Accepted:
            return
        target = Path(self.temp.name) / ("signature_" + uuid.uuid4().hex + ".png")
        try:
            dialog.export(target)
            placement = Placement(self.page_index, x, y, width, height, str(target))
            self.signatures.append(placement)
            self.queue.addItem(f"Page {self.page_index+1} | {width}x{height} pt")
            self.position = None
            self.redraw()
        except Exception as exc:
            QMessageBox.warning(self, "Signature failed", str(exc))
    def remove_selected(self):
        index = self.queue.currentRow()
        if index >= 0:
            self.signatures.pop(index)
            self.queue.takeItem(index)
            self.redraw()
    def save(self):
        if not self.signatures:
            QMessageBox.warning(self, "No signatures", "Capture at least one signature first.")
            return
        default = str(Path(self.source).with_name(Path(self.source).stem + "_signed.pdf"))
        output, _ = QFileDialog.getSaveFileName(self, "Save signed PDF", default, "PDF (*.pdf)")
        if not output:
            return
        if not output.lower().endswith(".pdf"):
            output += ".pdf"
        answer = QMessageBox.question(
            self, "Confirm signature placement",
            f"Save {len(self.signatures)} signature(s) into a new PDF?\n"
            "Review the page positions and sizes before continuing.\n"
            "The original document will not be overwritten.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            audit = sign_pdf_many(self.preview_pdf, self.signatures, output,
                                  source_document=self.source)
            QMessageBox.information(self, "Saved", "Signed PDF saved:\n" + output
                                    + "\n\nSignature-image audit:\n" + audit)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
    def closeEvent(self, event):
        if self.doc is not None:
            self.doc.close()
        self.temp.cleanup()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Window()
    window.show()
    sys.exit(app.exec())
