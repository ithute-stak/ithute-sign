"""IthuteSign offline Windows document-signing desktop.

Uses the official Wacom STU bridge when installed. Development mouse capture is
only available before creating the release-mode.flag production marker.
"""
import sys
import tempfile
import subprocess
import shutil
import uuid
from datetime import datetime
from dataclasses import replace
from pathlib import Path
import fitz
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QScrollArea, QSpinBox,
    QDialog, QDialogButtonBox, QListWidget)
from document import to_pdf, sign_pdf_many, Placement, sha256
from device import probe_bridge, show_screen, validate_signature_png
from geometry import fit_rectangle
from loanhub import detect_loanhub, save_loanhub_signed

def root_folder():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def bridge_path():
    root = root_folder()
    for candidate in (root / "wacom-bridge" / "linux" / "STUCapture",
                      root / "wacom-bridge" / "STUCapture.exe",
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
        buttons.accepted.connect(self.confirm_capture)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def clear(self):
        self.captured = None
        self.pad.clear()
        self.preview.setPixmap(QPixmap())
        self.preview.setText("No STU signature captured")
    def capture_stu(self):
        # A failed or cancelled recapture must never silently reuse an old signature.
        self.clear()
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
    def confirm_capture(self):
        if self.captured:
            try:
                validate_signature_png(self.captured)
            except Exception as exc:
                QMessageBox.warning(self, "Invalid signature", str(exc))
                return
        elif release_mode():
            QMessageBox.warning(self, "Signature required", "Capture a signature using the STU-540 first.")
            return
        elif self.pad.strokes < 2:
            QMessageBox.warning(self, "Signature required", "Draw a signature before continuing.")
            return
        self.accept()

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
        self.source_digest = None
        self.preview_pdf = None
        self.page_index = 0
        self.zoom = 1.2
        self.position = None
        self.signatures = []
        base = QWidget()
        self.setCentralWidget(base)
        layout = QHBoxLayout(base)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(248)
        menu = QVBoxLayout(sidebar)
        menu.setContentsMargins(16, 22, 16, 18)
        menu.setSpacing(9)
        brand = QLabel("ITHUTESIGN")
        brand.setObjectName("brand")
        menu.addWidget(brand)
        menu.addWidget(QLabel("OFFLINE SIGNING WORKSPACE"))
        menu.addSpacing(22)
        for title, actions in (
            ("DOCUMENTS", (("Open PDF / Word", self.open_document),
                           ("Auto-sign LoanHub", self.auto_sign_loanhub))),
            ("SIGNATURES", (("Add signature", self.add_signature),
                            ("Reuse selected signature", self.reuse_selected_signature),
                            ("Remove selected", self.remove_selected))),
            ("DEVICE & EXPORT", (("Device status", self.device_status),
                                 ("Save signed PDF", self.save)))):
            section = QLabel(title)
            section.setObjectName("section")
            menu.addWidget(section)
            for label, handler in actions:
                button = QPushButton(label)
                button.setObjectName("primary" if label in ("Auto-sign LoanHub", "Save signed PDF") else "menuButton")
                button.setMinimumHeight(42)
                button.setCursor(Qt.PointingHandCursor)
                button.clicked.connect(handler)
                menu.addWidget(button)
            menu.addSpacing(14)
        menu.addStretch()
        menu.addWidget(QLabel("LOCAL MODE  •  NO INTERNET REQUIRED"))
        layout.addWidget(sidebar)
        main = QWidget()
        main.setObjectName("mainArea")
        workspace = QVBoxLayout(main)
        workspace.setContentsMargins(24, 20, 24, 16)
        workspace.setSpacing(12)
        heading = QLabel("Document workspace")
        heading.setObjectName("pageHeading")
        workspace.addWidget(heading)
        navigation = QHBoxLayout()
        for label, handler in (("← Previous page", self.previous), ("Next page →", self.next)):
            button = QPushButton(label)
            button.clicked.connect(handler)
            navigation.addWidget(button)
        navigation.addStretch()
        self.page_label = QLabel("No document opened")
        navigation.addWidget(self.page_label)
        for label, change in (("−", -0.15), ("+", 0.15)):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, step=change: self.change_zoom(step))
            navigation.addWidget(button)
        fit_button = QPushButton("Fit width")
        fit_button.clicked.connect(self.fit_width)
        navigation.addWidget(fit_button)
        workspace.addLayout(navigation)
        options = QHBoxLayout()
        options.addWidget(QLabel("Signature width (pt)"))
        self.width = QSpinBox()
        self.width.setRange(30, 400)
        self.width.setValue(160)
        options.addWidget(self.width)
        options.addWidget(QLabel("Height (pt)"))
        self.height = QSpinBox()
        self.height.setRange(15, 180)
        self.height.setValue(65)
        options.addWidget(self.height)
        self.width.valueChanged.connect(self.resize_selected)
        self.height.valueChanged.connect(self.resize_selected)
        self.queue_selection_syncing = False
        options.addStretch()
        workspace.addLayout(options)
        content = QHBoxLayout()
        self.scroll = QScrollArea()
        self.page = PageView(self)
        self.scroll.setWidget(self.page)
        content.addWidget(self.scroll, 4)
        queue_panel = QVBoxLayout()
        queue_panel.addWidget(QLabel("Signature placements"))
        self.queue = QListWidget()
        self.queue.currentRowChanged.connect(self.select_signature)
        queue_panel.addWidget(self.queue)
        content.addLayout(queue_panel, 1)
        workspace.addLayout(content)
        layout.addWidget(main, 1)
        self.setStyleSheet("""
            QWidget#sidebar { background: #152941; color: white; }
            QWidget#sidebar QLabel { color: #b7c8db; font-weight: 600; }
            QLabel#brand { color: white; font-size: 23px; font-weight: 800; }
            QLabel#section { color: #8faac4; font-size: 11px; }
            QPushButton#menuButton, QPushButton#primary {
                text-align: left; padding: 9px 13px; border: none;
                border-radius: 8px; background: #203954; color: white;
                font-weight: 600;
            }
            QPushButton#menuButton:hover { background: #315473; }
            QPushButton#primary { background: #087e82; }
            QPushButton#primary:hover { background: #0b999c; }
            QWidget#mainArea { background: #eef2f7; color: #18304c; }
            QLabel#pageHeading { color: #18304c; font-size: 22px; font-weight: 750; }
            QWidget#mainArea QPushButton { padding: 8px 13px; }
            QWidget#mainArea QLabel { color: #263f5c; }
            QWidget#mainArea QSpinBox { background: white; color: #18304c;
                border: 1px solid #bdcbd9; border-radius: 5px; padding: 5px; }
            QWidget#mainArea QListWidget { background: white; border: 1px solid #d1dce8; border-radius: 8px; }
            QWidget#mainArea QScrollArea { border: 1px solid #d1dce8; background: #dce4ed; }
        """)
        self.status = QLabel("Connect STU-540. Open a document to begin.")
        self.status.setStyleSheet("color: #38546d; font-weight: 600; padding: 5px;")
        workspace.addWidget(self.status)
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
        if path:
            self.load_document(path)

    def load_document(self, path):
        """Open a document explicitly supplied by a trusted local desktop launch."""
        path = str(Path(path).resolve())
        if Path(path).suffix.lower() not in {".pdf", ".docx", ".doc"}:
            QMessageBox.critical(self, "Open failed", "Unsupported document type")
            return
        if not Path(path).is_file():
            QMessageBox.critical(self, "Open failed", "Document does not exist")
            return
        new_doc = None
        try:
            pdf = to_pdf(path, str(Path(self.temp.name) / (uuid.uuid4().hex + ".pdf")))
            new_doc = fitz.open(pdf)
            if not len(new_doc) or new_doc.needs_pass:
                raise ValueError("Document is empty or encrypted")
            if self.doc is not None:
                self.doc.close()
            self.doc = new_doc
            new_doc = None
            self.source = path
            self.source_digest = sha256(path)
            self.preview_pdf = pdf
            self.page_index = 0
            self.position = None
            self.signatures.clear()
            self.queue.clear()
            self.redraw()
        except Exception as exc:
            if new_doc is not None:
                new_doc.close()
            QMessageBox.critical(self, "Open failed", str(exc))
    def change_zoom(self, delta):
        if self.doc is not None:
            self.zoom = max(0.4, min(3.0, round(self.zoom + delta, 2)))
            self.redraw()

    def fit_width(self):
        if self.doc is not None:
            available = max(250, self.scroll.viewport().width() - 24)
            self.zoom = max(0.4, min(3.0, available / self.doc[self.page_index].rect.width))
            self.redraw()

    def redraw(self):
        if self.doc is None:
            return
        page = self.doc[self.page_index]
        self.page_label.setText(f"Page {self.page_index + 1} of {len(self.doc)} · {self.zoom * 100:.0f}%")
        pixels = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom))
        image = QPixmap.fromImage(QImage(pixels.samples, pixels.width, pixels.height,
                                        pixels.stride, QImage.Format_RGB888).copy())
        painter = QPainter(image)
        for signature_index, placement in enumerate(self.signatures):
            if placement.page_index != self.page_index:
                continue
            x, y = round(placement.x * self.zoom), round(placement.y * self.zoom)
            w, h = round(placement.width * self.zoom), round(placement.height * self.zoom)
            pix = QPixmap(placement.signature_png)
            if not pix.isNull():
                rx, ry, rw, rh = fit_rectangle(x, y, w, h, pix.width(), pix.height())
                painter.drawPixmap(QRectF(rx, ry, rw, rh), pix, QRectF(pix.rect()))
            selected = signature_index == self.queue.currentRow()
            painter.setPen(QPen(QColor("#e88d12" if selected else "#16935f"), 3 if selected else 2))
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
    def confirm_signer(self, title, description, confirm_text="Continue"):
        """Consistent, accessible offline signing confirmation dialog."""
        popup = QDialog(self)
        popup.setWindowTitle("IthuteSign — " + title)
        popup.setModal(True)
        popup.setMinimumWidth(440)
        popup.setStyleSheet("""
            QDialog { background: #f5f8fc; color: #18304c; }
            QLabel { color: #18304c; }
            QLabel#dialogHeading { font-size: 18px; font-weight: 700; }
            QLabel#dialogBody { font-size: 13px; }
            QPushButton { min-height: 37px; min-width: 105px; padding: 5px 15px;
                border-radius: 7px; border: 1px solid #bdcbd9; background: white;
                color: #18304c; font-weight: 600; }
            QPushButton#confirmButton { background: #087e82; color: white;
                border: 1px solid #087e82; }
        """)
        body = QVBoxLayout(popup)
        body.setContentsMargins(26, 24, 26, 22)
        body.setSpacing(15)
        heading = QLabel(title)
        heading.setObjectName("dialogHeading")
        body.addWidget(heading)
        message = QLabel(description)
        message.setObjectName("dialogBody")
        message.setWordWrap(True)
        message.setMinimumWidth(380)
        body.addWidget(message)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(popup.reject)
        buttons.addWidget(cancel)
        proceed = QPushButton(confirm_text)
        proceed.setObjectName("confirmButton")
        proceed.setDefault(True)
        proceed.clicked.connect(popup.accept)
        buttons.addWidget(proceed)
        body.addLayout(buttons)
        return popup.exec() == QDialog.Accepted

    def auto_sign_loanhub(self):
        """Offline, fail-closed workflow for the verified LoanHub contract layout."""
        if self.doc is None or not self.source or Path(self.source).suffix.lower() != ".pdf":
            QMessageBox.warning(self, "LoanHub", "Open a LoanHub PDF contract first.")
            return
        if self.signatures:
            QMessageBox.warning(self, "LoanHub", "Finish or reopen the document before automatic signing.")
            return
        try:
            if sha256(self.source) != self.source_digest:
                raise ValueError("Source PDF has changed since opening")
            pending = detect_loanhub(self.doc)
        except Exception as exc:
            QMessageBox.warning(self, "LoanHub template not recognized", str(exc))
            return
        if not pending:
            QMessageBox.information(self, "LoanHub", "No pending witness fields found.")
            return
        roles = "\\n".join("• " + f.role for f in pending)
        if not self.confirm_signer(
            "Review detected signatories",
            "The following fields require signatures on page 7:\\n\\n"
            + roles + "\\n\\nConfirm that the correct people are present."
            + "\\nExisting signed records will not be overwritten.",
            "Start signing"):
            return
        captured = []
        try:
            self.page_index = 6
            self.redraw()
            for field in pending:
                if not self.confirm_signer(
                    "Next signatory: " + field.role,
                    "Please ask the " + field.role
                    + " to sign on the Wacom STU-540.\\n\\n"
                    + "Only continue when the correct signer is ready.",
                    "Capture signature"):
                    return
                dialog = CaptureDialog(self.temp.name, self)
                if dialog.exec() != QDialog.Accepted:
                    return
                target = Path(self.temp.name) / ("loanhub_" + uuid.uuid4().hex + ".png")
                dialog.export(target)
                validate_signature_png(target)
                captured.append((field, str(target), datetime.now().astimezone()))
            default = str(Path(self.source).with_name(Path(self.source).stem + "_signed.pdf"))
            output, _ = QFileDialog.getSaveFileName(self, "Save LoanHub signed PDF", default, "PDF (*.pdf)")
            if not output:
                return
            if not output.lower().endswith(".pdf"):
                output += ".pdf"
            if sha256(self.source) != self.source_digest:
                raise ValueError("Source PDF changed during signing")
            signed = save_loanhub_signed(self.source, output, captured)
            QMessageBox.information(self, "LoanHub signed", "Signed PDF saved:\\n" + signed)
        except Exception as exc:
            QMessageBox.critical(self, "LoanHub signing failed", str(exc))

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
            validate_signature_png(target)
            placement = Placement(self.page_index, x, y, width, height, str(target))
            self.signatures.append(placement)
            self.queue_selection_syncing = True
            try:
                self.queue.addItem(f"Page {self.page_index+1} | {width}x{height} pt")
            finally:
                self.queue_selection_syncing = False
            self.position = None
            self.redraw()
        except Exception as exc:
            QMessageBox.warning(self, "Signature failed", str(exc))
    def reuse_selected_signature(self):
        """Place a previously captured signature elsewhere in this document.

        Reuse is intentionally limited to the currently opened document.
        """
        if self.doc is None or self.position is None:
            QMessageBox.warning(self, "Select position",
                                "Click the new signature location on the PDF first.")
            return
        index = self.queue.currentRow()
        if not (0 <= index < len(self.signatures)):
            QMessageBox.warning(self, "Select signature",
                                "Select an existing signature in the queue to reuse.")
            return
        original = self.signatures[index]
        if not Path(original.signature_png).is_file():
            QMessageBox.warning(self, "Signature unavailable",
                                "The original signature image is no longer available.")
            return
        x, y = self.position
        page = self.doc[self.page_index]
        width, height = original.width, original.height
        if x + width > page.rect.width or y + height > page.rect.height:
            QMessageBox.warning(self, "Position",
                                "Signature must fit within the page.")
            return
        placement = replace(original, page_index=self.page_index, x=x, y=y)
        self.signatures.append(placement)
        self.queue_selection_syncing = True
        try:
            self.queue.addItem(f"Page {self.page_index+1} | {width:g}x{height:g} pt")
        finally:
            self.queue_selection_syncing = False
        self.position = None
        self.redraw()

    def select_signature(self, index):
        if self.queue_selection_syncing or not (0 <= index < len(self.signatures)):
            return
        item = self.signatures[index]
        self.queue_selection_syncing = True
        try:
            self.width.setValue(round(item.width))
            self.height.setValue(round(item.height))
        finally:
            self.queue_selection_syncing = False
        if self.doc is not None and item.page_index != self.page_index:
            self.page_index = item.page_index
        self.redraw()

    def resize_selected(self, unused=None):
        if self.queue_selection_syncing or self.doc is None:
            return
        index = self.queue.currentRow()
        if not (0 <= index < len(self.signatures)):
            return
        item = self.signatures[index]
        page = self.doc[item.page_index]
        width, height = self.width.value(), self.height.value()
        if item.x + width > page.rect.width or item.y + height > page.rect.height:
            self.status.setText("Resize rejected: signature would extend outside the page")
            return
        self.signatures[index] = replace(item, width=width, height=height)
        self.queue.item(index).setText(f"Page {item.page_index+1} | {width}x{height} pt")
        self.redraw()

    def remove_selected(self):
        index = self.queue.currentRow()
        if 0 <= index < len(self.signatures):
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
        try:
            if sha256(self.source) != self.source_digest:
                raise ValueError("The source document changed after opening. Reopen it before signing.")
        except Exception as exc:
            QMessageBox.critical(self, "Source changed or unavailable", str(exc))
            return
        answer = QMessageBox.question(
            self, "Confirm signature placement",
            f"Save {len(self.signatures)} signature(s) into a new PDF?\\n"
            "Review the page positions and sizes before continuing.\\n"
            "The original document will not be overwritten.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            signed_pdf = sign_pdf_many(self.preview_pdf, self.signatures, output,
                                       source_document=self.source)
            QMessageBox.information(self, "Saved", "Signed PDF saved:\\n" + signed_pdf)
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
    # Explicit --open prevents accidental interpretation of Qt or other flags as paths.
    if len(sys.argv) == 3 and sys.argv[1] == "--open":
        window.load_document(sys.argv[2])
    sys.exit(app.exec())
