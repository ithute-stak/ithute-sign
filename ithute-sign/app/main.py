"""IthuteSign offline Windows document-signing desktop.

Uses the official Wacom STU bridge when installed. Development mouse capture is
only available before creating the release-mode.flag production marker.
"""
import sys
import tempfile
import subprocess
import shutil
import uuid
import os
from datetime import datetime
from dataclasses import replace
from pathlib import Path
import pymupdf as fitz
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QScrollArea, QSpinBox,
    QDialog, QDialogButtonBox, QListWidget, QProgressBar, QStackedWidget, QStyle, QInputDialog)
from document import to_pdf, sign_pdf_many, Placement, sha256
from local_login_dialog import LocalLoginDialog, default_user_db
from local_users import LocalUsers
from signature_vault import SignatureVault
from signature_authorization_dialog import SignatureAuthorizationDialog
from loanhub_preflight_dialog import LoanHubPreflightDialog
from PySide6.QtWidgets import QLineEdit
from device import probe_bridge, show_screen, validate_signature_png
from geometry import fit_rectangle
from loanhub import detect_loanhub, save_loanhub_signed
from loanhub_login_dialog import LoanHubLoginDialog
from loanhub_company_identity import company_for_user
from loanhub_auth import LoanHubLoginTransport
from loanhub_presentation import employee_display_name
from loanhub_loans_dialog import LoanHubLoansDialog
from whatsapp_dialog import WhatsAppDeliveryDialog
from imail_dialog import IMailDeliveryDialog
from signed_library import archive_signed_pdf, list_signed_pdfs, verify_archived_pdf, extract_national_ids, normalize_national_id

def decorate_action(button, label):
    """Use native Qt icons so Linux and Windows need no extra icon packages."""
    icons = {
        "Log in to LoanHub": QStyle.SP_DialogApplyButton,
        "Log out of LoanHub": QStyle.SP_DialogCancelButton,
        "Open PDF / Word": QStyle.SP_DialogOpenButton,
        "Auto-sign LoanHub": QStyle.SP_FileDialogDetailedView,
        "Add signature": QStyle.SP_FileDialogNewFolder,
        "Reuse selected signature": QStyle.SP_BrowserReload,
        "Remove selected": QStyle.SP_TrashIcon,
        "Device status": QStyle.SP_ComputerIcon,
        "Save signed PDF": QStyle.SP_DialogSaveButton,
        "Check Wacom": QStyle.SP_ComputerIcon,
    }
    icon = icons.get(label)
    if icon is not None:
        button.setIcon(button.style().standardIcon(icon))
    button.setCursor(Qt.PointingHandCursor)
    return button


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
        self.setWindowTitle("IthuteSign — Offline LoanHub signing | build 2026.11.18-B")
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
        self.recent_documents = []
        self.last_signed_pdf = None
        self.loanhub_access_token = None
        self.loanhub_user = None
        self.loanhub_company = None
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
        self.local_signature_button = QPushButton("My stored signature")
        self.local_signature_button.setMinimumHeight(38)
        self.local_signature_button.clicked.connect(self.enroll_local_signature)
        menu.addWidget(self.local_signature_button)
        self.use_stored_signature_button = QPushButton("Use my stored signature")
        self.use_stored_signature_button.setMinimumHeight(38)
        self.use_stored_signature_button.clicked.connect(self.use_local_signature)
        menu.addWidget(self.use_stored_signature_button)
        login_button = QPushButton("Log in to LoanHub")
        decorate_action(login_button, "Log in to LoanHub")
        login_button.setObjectName("primary")
        login_button.setMinimumHeight(42)
        login_button.clicked.connect(self.toggle_loanhub_session)
        self.loanhub_session_button = login_button
        menu.addWidget(login_button)
        self.loanhub_login_status = QLabel("LoanHub: Not signed in")
        self.loanhub_login_status.setWordWrap(True)
        self.loanhub_login_status.setObjectName("sidebarDetail")
        menu.addWidget(self.loanhub_login_status)
        menu.addSpacing(22)
        for title, actions in (
            ("DOCUMENTS", (("Open PDF / Word", self.open_document),
                           ("Auto-sign LoanHub", self.auto_sign_loanhub),
                           ("Signed document library", self.open_signed_library),
                           ("Email signed PDF via iMail", self.send_signed_imail))),
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
                decorate_action(button, label)
                button.clicked.connect(handler)
                menu.addWidget(button)
            menu.addSpacing(14)
        menu.addStretch()
        status_title = QLabel("DOCUMENT STATUS")
        status_title.setObjectName("section")
        menu.addWidget(status_title)
        self.sidebar_document = QLabel("No document opened")
        self.sidebar_document.setWordWrap(True)
        self.sidebar_document.setObjectName("sidebarDetail")
        menu.addWidget(self.sidebar_document)
        self.sidebar_progress = QLabel("Signatures: 0")
        self.sidebar_progress.setObjectName("sidebarDetail")
        menu.addWidget(self.sidebar_progress)
        self.sidebar_ready = QLabel("Open a document to begin")
        self.sidebar_ready.setWordWrap(True)
        self.sidebar_ready.setObjectName("sidebarDetail")
        menu.addWidget(self.sidebar_ready)
        self.sidebar_device = QLabel("Wacom: checking…")
        self.sidebar_device.setObjectName("sidebarDetail")
        menu.addWidget(self.sidebar_device)
        menu.addSpacing(10)
        layout.addWidget(sidebar)
        main = QWidget()
        main.setObjectName("mainArea")
        workspace = QVBoxLayout(main)
        workspace.setContentsMargins(24, 20, 24, 16)
        workspace.setSpacing(12)
        self.screen_stack = QStackedWidget()
        workspace.addWidget(self.screen_stack, 1)
        self.home_panel = QWidget()
        self.home_panel.setObjectName("homePanel")
        home = QVBoxLayout(self.home_panel)
        home.setContentsMargins(32, 30, 32, 30)
        home.setSpacing(12)
        welcome_title = QLabel("Signing workspace")
        welcome_title.setObjectName("pageHeading")
        home.addWidget(welcome_title)
        self.loanhub_account_name = QLabel("Sign in to LoanHub to get started")
        self.loanhub_account_name.setObjectName("homeSubtitle")
        home.addWidget(self.loanhub_account_name)
        self.loanhub_account_note = QLabel("")
        self.loanhub_account_note.setObjectName("homeNotice")
        self.loanhub_account_note.setWordWrap(True)
        self.loanhub_account_note.setVisible(False)
        home.addWidget(self.loanhub_account_note)
        home.addSpacing(20)
        quick_heading = QLabel("QUICK ACTIONS")
        quick_heading.setObjectName("homeSection")
        home.addWidget(quick_heading)
        shortcuts = QHBoxLayout()
        for label, handler in (("Open PDF / Word", self.open_document),
                               ("Auto-sign LoanHub", self.open_loanhub_from_home),
                               ("Check Wacom", self.device_status)):
            action = QPushButton(label)
            action.setMinimumHeight(64)
            action.setObjectName("quickAction")
            decorate_action(action, label)
            action.clicked.connect(handler)
            shortcuts.addWidget(action)
        home.addLayout(shortcuts)
        self.home_device = QLabel("Wacom STU-540 · Checking connection…")
        self.home_device.setObjectName("homeDevice")
        home.addWidget(self.home_device)
        home.addSpacing(22)
        recent_heading = QLabel("RECENT DOCUMENTS")
        recent_heading.setObjectName("homeSection")
        loans_button = QPushButton("Loans & contracts")
        decorate_action(loans_button, "Auto-sign LoanHub")
        loans_button.setObjectName("quickAction")
        loans_button.setMinimumHeight(56)
        loans_button.clicked.connect(self.open_loanhub_loans)
        home.addWidget(loans_button)
        whatsapp_button = QPushButton("Send signed PDF via WhatsApp")
        whatsapp_button.setObjectName("quickAction")
        whatsapp_button.setMinimumHeight(56)
        whatsapp_button.clicked.connect(self.send_signed_whatsapp)
        home.addWidget(whatsapp_button)
        imail_button = QPushButton("Email signed PDF via iMail")
        imail_button.setObjectName("quickAction")
        imail_button.setMinimumHeight(56)
        imail_button.clicked.connect(self.send_signed_imail)
        home.addWidget(imail_button)
        home.addWidget(recent_heading)
        self.home_recent = QLabel("No documents opened yet")
        self.home_recent.setWordWrap(True)
        home.addWidget(self.home_recent)
        self.home_recent_buttons = []
        for _ in range(3):
            recent_button = QPushButton()
            recent_button.setObjectName("recentButton")
            recent_button.setVisible(False)
            recent_button.clicked.connect(
                lambda checked=False, button=recent_button:
                self.load_document(button.property("document_path")))
            home.addWidget(recent_button)
            self.home_recent_buttons.append(recent_button)
        home.addStretch(1)
        self.screen_stack.addWidget(self.home_panel)
        self.document_panel = QWidget()
        document_layout = QVBoxLayout(self.document_panel)
        document_layout.setContentsMargins(0, 0, 0, 0)
        document_layout.setSpacing(12)
        heading = QLabel("Document workspace")
        heading.setObjectName("pageHeading")
        document_layout.addWidget(heading)
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
        document_layout.addLayout(navigation)
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
        document_layout.addLayout(options)
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
        queue_panel.addWidget(QLabel("Signing progress"))
        self.workspace_progress = QProgressBar()
        self.workspace_progress.setRange(0, 1)
        self.workspace_progress.setValue(0)
        queue_panel.addWidget(self.workspace_progress)
        self.workspace_hint = QLabel("Open a document to begin")
        self.workspace_hint.setWordWrap(True)
        self.workspace_hint.setObjectName("workspaceHint")
        queue_panel.addWidget(self.workspace_hint)
        self.signature_preview = QLabel("Select a signature to preview")
        self.signature_preview.setAlignment(Qt.AlignCenter)
        self.signature_preview.setMinimumHeight(95)
        self.signature_preview.setObjectName("signaturePreview")
        queue_panel.addWidget(self.signature_preview)
        content.addLayout(queue_panel, 1)
        document_layout.addLayout(content, 1)
        self.screen_stack.addWidget(self.document_panel)
        self.screen_stack.setCurrentWidget(self.home_panel)
        layout.addWidget(main, 1)
        self.setStyleSheet("""
            QWidget#sidebar { background: #152941; color: white; }
            QWidget#sidebar QLabel { color: #b7c8db; font-weight: 600; }
            QLabel#brand { color: white; font-size: 23px; font-weight: 800; }
            QLabel#section { color: #8faac4; font-size: 11px; }
            QLabel#sidebarDetail { color: #e0ebf5; font-size: 12px; padding: 2px 0; }
            QPushButton#menuButton, QPushButton#primary {
                text-align: left; padding: 9px 13px; border: none;
                border-radius: 8px; background: #203954; color: white;
                font-weight: 600;
            }
            QPushButton#menuButton:hover { background: #315473; }
            QPushButton#primary { background: #087e82; }
            QPushButton#primary:hover { background: #0b999c; }
            QWidget#mainArea { background: #eef2f7; color: #18304c; }
            QWidget#homePanel { background: white; border: 1px solid #e0e7f0; border-radius: 16px; }
            QLabel#homeSubtitle { color: #71839a; font-size: 14px; }
            QLabel#homeSection { color: #71839a; font-size: 11px; font-weight: 800; }
            QLabel#homeNotice { background: #fff3e7; color: #915518; padding: 12px; border-radius: 9px; }
            QPushButton#quickAction { background: #f6f9fd; color: #17324f; border: 1px solid #dbe5f0;
                border-radius: 12px; font-size: 13px; font-weight: 700; }
            QPushButton#quickAction:hover { background: #e9f5f5; border-color: #0b9290; }
            QLabel#homeDevice { background: #e7f4f3; color: #13565c; padding: 15px; border-radius: 8px; font-weight: 700; }
            QPushButton#recentButton { text-align: left; background: #f1f6fb; color: #18304c; border: 1px solid #d1dce8; border-radius: 7px; }
            QLabel#pageHeading { color: #18304c; font-size: 22px; font-weight: 750; }
            QWidget#mainArea QPushButton { padding: 8px 13px; }
            QWidget#mainArea QLabel { color: #263f5c; }
            QWidget#mainArea QSpinBox { background: white; color: #18304c;
                border: 1px solid #bdcbd9; border-radius: 5px; padding: 5px; }
            QWidget#mainArea QListWidget { background: white; border: 1px solid #d1dce8; border-radius: 8px; }
            QLabel#workspaceHint { color: #52677f; font-size: 12px; }
            QLabel#signaturePreview { background: white; border: 1px dashed #bdcbd9; border-radius: 8px; }
            QWidget#mainArea QProgressBar { background: #dce4ed; border-radius: 6px; text-align: center; }
            QWidget#mainArea QProgressBar::chunk { background: #087e82; border-radius: 6px; }
            QWidget#mainArea QScrollArea { border: 1px solid #d1dce8; background: #dce4ed; }
        """)
        self.status = QLabel("Connect STU-540. Open a document to begin.")
        self.status.setStyleSheet("color: #38546d; font-weight: 600; padding: 5px;")
        workspace.addWidget(self.status)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, self.welcome)
    def refresh_workspace_progress(self):
        if self.doc is None:
            self.workspace_progress.setRange(0, 1)
            self.workspace_progress.setValue(0)
            self.workspace_hint.setText("Open a document to begin")
        else:
            count = len(self.signatures)
            # Manual signing has no known required-field total; never
            # misrepresent a placement count as contract completion.
            self.workspace_progress.setRange(0, max(1, count))
            self.workspace_progress.setValue(count)
            self.workspace_hint.setText(
                f"{count} manual placement(s) queued. "
                "Review the PDF and save when all required signers have signed."
                if count else "No manual placements yet. Use Add signature or Auto-sign LoanHub.")
        index = self.queue.currentRow()
        if 0 <= index < len(self.signatures):
            pix = QPixmap(self.signatures[index].signature_png)
            if not pix.isNull():
                self.signature_preview.setPixmap(pix.scaled(
                    210, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.signature_preview.setText("")
                return
        self.signature_preview.setPixmap(QPixmap())
        self.signature_preview.setText("Select a signature to preview")

    def refresh_document_status(self):
        if self.doc is None:
            self.sidebar_document.setText("No document opened")
            self.sidebar_progress.setText("Signatures: 0")
            self.sidebar_ready.setText("Open a document to begin")
            return
        self.sidebar_document.setText(Path(self.source).name if self.source else "Document")
        count = len(self.signatures)
        self.sidebar_progress.setText(f"Manual placements: {count}")
        if count:
            self.sidebar_ready.setText("Manual signatures queued · Save PDF when ready")
        else:
            self.sidebar_ready.setText("No manual signatures queued · Use Add signature or Auto-sign LoanHub")

    def refresh_recent_documents(self):
        self.home_recent.setText(
            "Choose a document below to reopen it."
            if self.recent_documents else "No documents opened yet")
        for button, path in zip(self.home_recent_buttons, self.recent_documents):
            button.setText(Path(path).name)
            button.setProperty("document_path", path)
        for i, button in enumerate(self.home_recent_buttons):
            button.setVisible(i < len(self.recent_documents))

    def welcome(self):
        result = show_screen(bridge_path(), "welcome")
        self.status.setText("STU-540 welcome screen ready" if result.connected
                            else "STU-540: " + result.message)
        self.sidebar_device.setText("Wacom: connected" if result.connected else "Wacom: disconnected")
        self.home_device.setText("●  Wacom STU-540 connected" if result.connected
                                 else "○  Wacom STU-540 disconnected — Check device")
    def device_status(self):
        result = probe_bridge(bridge_path())
        self.sidebar_device.setText("Wacom: connected" if result.connected else "Wacom: disconnected")
        QMessageBox.information(self, "Device connection",
                                ("Connected" if result.connected else "Disconnected")
                                + "\n" + result.message)
    def open_document(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open document", "",
                                             "Documents (*.pdf *.docx *.doc)")
        if path:
            self.load_document(path)

    def open_loanhub_from_home(self):
        if self.doc is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open LoanHub contract", "", "PDF (*.pdf)")
            if not path:
                return
            self.load_document(path)
            if self.doc is None or self.source != str(Path(path).resolve()):
                return
        self.auto_sign_loanhub()

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
            self.last_signed_pdf = None
            self.last_signed_pdf_digest = None
            self.last_signed_source = None
            self.recent_documents = ([path] + [p for p in self.recent_documents if p != path])[:3]
            self.refresh_recent_documents()
            self.source_digest = sha256(path)
            self.preview_pdf = pdf
            self.page_index = 0
            self.position = None
            self.signatures.clear()
            self.queue.clear()
            self.redraw()
            self.refresh_document_status()
            self.refresh_workspace_progress()
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
        self.refresh_document_status()
        self.refresh_workspace_progress()
        self.screen_stack.setCurrentWidget(self.document_panel)
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
    def show_loanhub_progress(self, pending, completed=(), selected_roles=(), next_role=None):
        """Show prepared stored signatures separately from pending tablet captures."""
        completed_roles = set(completed)
        selected_roles = set(selected_roles)
        remaining = [field for field in pending if field.role not in completed_roles]
        if not remaining:
            return True
        if next_role is None:
            next_role = remaining[0].role
        dlg = QDialog(self)
        dlg.setWindowTitle("IthuteSign — LoanHub signing")
        dlg.setMinimumWidth(520)
        dlg.setStyleSheet("""
            QDialog { background: #f5f8fc; color: #18304c; }
            QLabel { color: #18304c; font-size: 13px; }
            QLabel#heading { font-size: 20px; font-weight: 750; }
            QListWidget { background: white; color: #18304c; border: 1px solid #cbd8e6;
                border-radius: 9px; padding: 8px; font-size: 13px; }
            QProgressBar { background: #e2eaf2; border: none; border-radius: 7px;
                height: 14px; text-align: center; color: #18304c; }
            QProgressBar::chunk { background: #087e82; border-radius: 7px; }
            QPushButton { padding: 10px 18px; border-radius: 7px;
                background: white; color: #18304c; border: 1px solid #cbd8e6;
                font-weight: 700; }
            QPushButton#captureNext { background: #087e82; color: white;
                border: 1px solid #087e82; }
        """)
        body = QVBoxLayout(dlg)
        body.setContentsMargins(26, 24, 26, 24)
        heading = QLabel("LoanHub signature checklist")
        heading.setObjectName("heading")
        body.addWidget(heading)
        body.addWidget(QLabel("Page 7 · Annexure C · Offline signing"))
        checklist = QListWidget()
        for field in pending:
            if field.role in completed_roles:
                status = ("✓  Stored signature prepared  —  "
                          if field.role in selected_roles else "✓  Tablet signature captured  —  ")
            elif field.role in selected_roles:
                status = "◉  Stored signature selected  —  "
            else:
                status = "○  Awaiting tablet signature  —  "
            checklist.addItem(status + field.role)
        checklist.setMinimumHeight(min(260, 52 * len(pending) + 20))
        body.addWidget(checklist)
        progress = QProgressBar()
        progress.setRange(0, len(pending))
        progress.setValue(len(completed_roles))
        body.addWidget(progress)
        instruction = QLabel("Next: " + next_role + ". Confirm this person is present "
                             "and ready to sign using the Wacom STU-540.")
        instruction.setWordWrap(True)
        body.addWidget(instruction)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel signing")
        cancel.clicked.connect(dlg.reject)
        actions.addWidget(cancel)
        capture = QPushButton("Capture " + next_role)
        capture.setObjectName("captureNext")
        capture.setDefault(True)
        capture.clicked.connect(dlg.accept)
        actions.addWidget(capture)
        body.addLayout(actions)
        return dlg.exec() == QDialog.Accepted

    def review_loanhub_signatures(self, pending, captured):
        """Review every newly captured signature before writing a PDF."""
        if len(captured) != len(pending):
            return False
        expected = {field.role for field in pending}
        if len(expected) != len(pending) or {field.role for field, _, _, _ in captured} != expected:
            return False
        popup = QDialog(self)
        popup.setWindowTitle("IthuteSign — Review before saving")
        popup.setMinimumWidth(570)
        popup.setStyleSheet("""
            QDialog { background: #f5f8fc; color: #18304c; }
            QLabel { color: #18304c; }
            QLabel#reviewTitle { font-size: 20px; font-weight: 750; }
            QLabel#reviewNote { color: #52677f; font-size: 12px; }
            QPushButton { min-height: 38px; padding: 7px 16px;
                border-radius: 7px; background: white; color: #18304c;
                border: 1px solid #cbd8e6; font-weight: 600; }
            QPushButton#saveButton { background: #087e82; color: white;
                border: 1px solid #087e82; }
        """)
        body = QVBoxLayout(popup)
        body.setContentsMargins(24, 22, 24, 22)
        heading = QLabel("Review captured signatures")
        heading.setObjectName("reviewTitle")
        body.addWidget(heading)
        note = QLabel("All required signatures for this signing session must be present. "
                      "Existing signed fields will be preserved.")
        note.setWordWrap(True)
        note.setObjectName("reviewNote")
        body.addWidget(note)
        for field, png, accepted, method in captured:
            validate_signature_png(png)
            row = QHBoxLayout()
            details = QVBoxLayout()
            details.addWidget(QLabel(field.role + "  ·  Captured"))
            details.addWidget(QLabel(accepted.strftime("%d %b %Y  %H:%M %Z")))
            row.addLayout(details, 2)
            picture = QLabel()
            picture.setMinimumSize(170, 52)
            picture.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(png)
            if pixmap.isNull():
                return False
            picture.setPixmap(pixmap.scaled(170, 52, Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation))
            row.addWidget(picture, 1)
            body.addLayout(row)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(popup.reject)
        actions.addWidget(cancel)
        approve = QPushButton("Approve & choose PDF")
        approve.setObjectName("saveButton")
        approve.setDefault(True)
        approve.clicked.connect(popup.accept)
        actions.addWidget(approve)
        body.addLayout(actions)
        return popup.exec() == QDialog.Accepted

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

    def show_loanhub_completion(self, signed, captured):
        """Report only successfully verified exports; opening is user initiated."""
        output = Path(signed)
        if not output.is_file():
            raise FileNotFoundError("Completed PDF could not be found")
        dlg = QDialog(self)
        dlg.setWindowTitle("IthuteSign — Contract completed")
        dlg.setMinimumWidth(500)
        dlg.setStyleSheet("""
            QDialog { background: #f5f8fc; color: #18304c; }
            QLabel { color: #18304c; }
            QLabel#completeTitle { font-size: 21px; font-weight: 750; }
            QLabel#completePath { color: #52677f; font-size: 12px; }
            QPushButton { padding: 10px 15px; border-radius: 7px;
                background: white; color: #18304c; border: 1px solid #cbd8e6;
                font-weight: 650; }
            QPushButton#openCompleted { background: #087e82; color: white;
                border: 1px solid #087e82; }
        """)
        body = QVBoxLayout(dlg)
        body.setContentsMargins(26, 24, 26, 24)
        title = QLabel("Signed PDF saved successfully")
        title.setObjectName("completeTitle")
        body.addWidget(title)
        body.addWidget(QLabel("✓  PDF export and signature checks passed"))
        body.addWidget(QLabel(f"✓  {len(captured)} new signature(s) captured"))
        body.addWidget(QLabel("✓  Original document preserved"))
        path_label = QLabel(str(output))
        path_label.setObjectName("completePath")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.addWidget(path_label)
        actions = QHBoxLayout()
        actions.addStretch()
        close = QPushButton("Done")
        close.clicked.connect(dlg.accept)
        actions.addWidget(close)
        open_button = QPushButton("Open signed PDF")
        open_button.setObjectName("openCompleted")
        def open_signed():
            try:
                if sys.platform.startswith("linux"):
                    subprocess.Popen(["xdg-open", str(output)], start_new_session=True)
                elif sys.platform == "win32":
                    os.startfile(str(output))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(output)], start_new_session=True)
                else:
                    raise RuntimeError("Opening PDFs is not supported on this platform")
                dlg.accept()
            except Exception as exc:
                QMessageBox.warning(dlg, "Cannot open PDF", str(exc))
        open_button.clicked.connect(open_signed)
        actions.addWidget(open_button)
        body.addLayout(actions)
        dlg.exec()

    def logout_loanhub(self):
        """Clear all LoanHub identity and company state before account switching."""
        self.loanhub_access_token = None
        self.loanhub_user = None
        self.loanhub_company = None
        self.last_signed_pdf = None
        self.last_signed_pdf_digest = None
        self.last_signed_source = None
        self.loanhub_login_status.setText("LoanHub: Not signed in")
        if hasattr(self, "loanhub_session_button"):
            self.loanhub_session_button.setText("Log in to LoanHub")
            decorate_action(self.loanhub_session_button, "Log in to LoanHub")
            self.loanhub_session_button.setObjectName("primary")
            self.loanhub_session_button.style().unpolish(self.loanhub_session_button)
            self.loanhub_session_button.style().polish(self.loanhub_session_button)
        if hasattr(self, "loanhub_account_name"):
            self.loanhub_account_name.setText("Sign in to LoanHub to get started")
            self.loanhub_account_note.setText("")
            self.loanhub_account_note.setVisible(False)
        if hasattr(self, "screen_stack") and hasattr(self, "home_panel"):
            self.screen_stack.setCurrentWidget(self.home_panel)

    def toggle_loanhub_session(self):
        if self.loanhub_access_token:
            self.logout_loanhub()
        else:
            self.open_loanhub_login()

    def open_loanhub_login(self):
        """Open existing LoanHub authentication UI; do not imply an active session."""
        # Reauthentication must never retain the previous employee's session.
        self.logout_loanhub()
        dialog = LoanHubLoginDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.access_token and dialog.verified_user:
            self.loanhub_session_button.setText("Log out of LoanHub")
            decorate_action(self.loanhub_session_button, "Log out of LoanHub")
            self.loanhub_session_button.setObjectName("menuButton")
            self.loanhub_session_button.style().unpolish(self.loanhub_session_button)
            self.loanhub_session_button.style().polish(self.loanhub_session_button)
            self.loanhub_access_token = dialog.access_token
            self.loanhub_user = dialog.verified_user
            self.loanhub_login_status.setText("LoanHub: Identity verified (company not selected)")
            display = employee_display_name(self.loanhub_user)
            self.loanhub_account_name.setText("Welcome, " + str(display))
            self.loanhub_account_note.setText("")
            self.loanhub_account_note.setVisible(False)
            self.screen_stack.setCurrentWidget(self.home_panel)
            self.identify_loanhub_company()

    def identify_loanhub_company(self):
        """Resolve tenant from the verified LoanHub user; never ask staff to pick."""
        self.loanhub_company = company_for_user(self.loanhub_user)
        if self.loanhub_company:
            try:
                company_id = self.loanhub_company["id"]
                details = LoanHubLoginTransport("https://api.loanhub.co.ls").get_authenticated(
                    "/api/v1/companies/" + company_id, self.loanhub_access_token)
                if str(details.get("id")) != company_id or details.get("is_active") is False:
                    raise ValueError("Company identity mismatch")
                name = details.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Company name missing")
                self.loanhub_company["name"] = name.strip()
            except Exception:
                self.loanhub_company = None
                self.loanhub_login_status.setText("LoanHub: Company details unavailable")
                self.loanhub_account_note.setText("Company details could not be verified.")
                self.loanhub_account_note.setVisible(True)
                return
            self.loanhub_login_status.setText("LoanHub: " + self.loanhub_company["name"])
            self.loanhub_account_note.setText("")
            self.loanhub_account_note.setVisible(False)
        else:
            self.loanhub_login_status.setText("LoanHub: Company could not be verified")
            self.loanhub_account_note.setText("Your company could not be verified.")
            self.loanhub_account_note.setVisible(True)

    def open_loanhub_loans(self):
        if not self.loanhub_access_token or not self.loanhub_company:
            QMessageBox.warning(self, "LoanHub", "Sign in and verify your company first.")
            return
        LoanHubLoansDialog(self.loanhub_access_token, self.loanhub_company, self).exec()

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
            QMessageBox.information(self, "LoanHub", "No pending signature fields found.")
            return
        try:
            from loanhub import inspect_loanhub_signatures
            inspection = inspect_loanhub_signatures(self.doc)
            employee = getattr(self, "local_user", None)
            name = employee["display_name"] if employee else "Not signed in"
            preflight = LoanHubPreflightDialog(
                inspection, name, bool(getattr(self, "session_signature", None)), self)
            if preflight.exec() != QDialog.Accepted:
                return
        except Exception as exc:
            QMessageBox.warning(self, "LoanHub inspection failed", str(exc))
            return
        captured = []
        try:
            self.page_index = 6
            self.redraw()
            # Prepare the employee's authorized lender signature first, before
            # asking anyone to sign on the Wacom tablet. This avoids confusing
            # the employee with a borrower/witness capture screen at startup.
            pending = sorted(pending, key=lambda field:
                0 if field.role == "Lender execution" else
                1 if field.role == "Borrower execution" else 2)
            employee = getattr(self, "local_user", None)
            enrolled = getattr(self, "session_signature", None)
            reusable_roles = {"Lender execution", "Borrower witness", "Lender witness"}
            reusable = [field for field in pending if field.role in reusable_roles]
            # Witness names in this fixed template must match the signed-in
            # employee. A lender signature also needs explicit authorization.
            witness_name_boxes = {
                "Borrower witness": fitz.Rect(400, 246, 539, 272),
                "Lender witness": fitz.Rect(400, 383, 539, 410),
            }
            selected_roles = set()
            if reusable and employee and enrolled:
                options = []
                expected = " ".join(employee["display_name"].split()).casefold()
                for field in reusable:
                    if field.role in witness_name_boxes:
                        named = " ".join(self.doc[6].get_textbox(
                            witness_name_boxes[field.role]).split())
                        eligible = named.casefold() == expected
                        reason = ("Assigned witness: " + named + ". Confirm you personally witnessed this signing."
                                  if eligible else "Assigned to " + named + "; cannot use this employee signature.")
                    else:
                        eligible = True
                        reason = ("Only select if you have authority to execute for the lender. "
                                  "The printed lender representative may be another person.")
                    options.append((field.role, eligible, reason))
                consent = SignatureAuthorizationDialog(employee["display_name"], options, self)
                if consent.exec() != QDialog.Accepted:
                    return
                selected_roles = consent.selected_roles
            # Prepare every selected employee signature before prompting for
            # tablet capture, so the checklist reflects all selections.
            pending = sorted(pending, key=lambda field: (
                0 if field.role in selected_roles else 1,
                0 if field.role == "Borrower execution" else 1))
            for field in pending:
                if field.role in selected_roles and employee and enrolled:
                    target = Path(self.temp.name) / ("loanhub_employee_" + uuid.uuid4().hex + ".png")
                    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as out:
                        out.write(enrolled)
                    validate_signature_png(target)
                    captured.append((field, str(target), datetime.now().astimezone(), "Stored employee signature"))
                    continue
                if not self.show_loanhub_progress(
                        pending, [entry[0].role for entry in captured],
                        selected_roles=selected_roles, next_role=field.role):
                    return
                dialog = CaptureDialog(self.temp.name, self)
                if dialog.exec() != QDialog.Accepted:
                    return
                target = Path(self.temp.name) / ("loanhub_" + uuid.uuid4().hex + ".png")
                dialog.export(target)
                validate_signature_png(target)
                captured.append((field, str(target), datetime.now().astimezone(), "Wacom STU-540"))
            if not self.review_loanhub_signatures(pending, captured):
                return
            if sha256(self.source) != self.source_digest:
                raise ValueError("Source PDF changed during signing")
            with tempfile.TemporaryDirectory(prefix="ithutesign_loanhub_") as temporary:
                output = str(Path(temporary) / (Path(self.source).stem + "_signed.pdf"))
                signed = save_loanhub_signed(self.source, output, captured)
                ids = extract_national_ids(signed)
                if len(ids) == 1:
                    national_id = ids[0]
                    confirmation = QMessageBox.question(
                        self, "Confirm client National ID",
                        "File this signed LoanHub document under National ID: " + national_id + "?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if confirmation != QMessageBox.Yes:
                        return
                else:
                    explanation = ("Multiple National IDs were detected." if ids else
                                   "No labelled National ID was detected.")
                    entered, accepted = QInputDialog.getText(
                        self, "Client National ID",
                        explanation + "\\nEnter the CLIENT'S National ID from the contract:")
                    if not accepted:
                        return
                    national_id = normalize_national_id(entered)
                archived = archive_signed_pdf(signed, national_id=national_id)
            self.last_signed_pdf = str(archived)
            self.last_signed_pdf_digest = sha256(archived)
            self.last_signed_source = self.source
            self.show_loanhub_completion(archived, captured)
        except Exception as exc:
            QMessageBox.critical(self, "LoanHub signing failed", str(exc))

    def use_local_signature(self):
        """Explicit, password-confirmed placement on the current local document only.

        LoanHub lender/witness role authorization is intentionally NOT inferred
        from local authentication; this action does not assert such a role.
        """
        user = getattr(self, "local_user", None)
        if not user:
            QMessageBox.warning(self, "Sign in required", "Local authentication is required.")
            return
        if self.doc is None or self.position is None:
            QMessageBox.warning(self, "Select position",
                "Open a document and click where your signature should be placed.")
            return
        x, y = self.position
        width, height = self.width.value(), self.height.value()
        page = self.doc[self.page_index]
        if x + width > page.rect.width or y + height > page.rect.height:
            QMessageBox.warning(self, "Position", "Signature must fit within the page.")
            return
        password, ok = QInputDialog.getText(self, "Authorize signature",
            "Re-enter your local password to unlock your stored signature:",
            QLineEdit.Password)
        if not ok:
            return
        store = LocalUsers(default_user_db())
        try:
            verified = store.authenticate(user["username"], password)
            if not verified or verified["id"] != user["id"]:
                QMessageBox.warning(self, "Authentication failed", "Incorrect password.")
                return
        finally:
            store.close()
        vault = SignatureVault(default_user_db())
        try:
            png = vault.decrypt(user["id"], password)
        except Exception as exc:
            QMessageBox.warning(self, "Signature unavailable", str(exc))
            return
        finally:
            vault.close()
        answer = QMessageBox.question(self, "Confirm signature placement",
            f"Place the registered signature of {user['display_name']} "
            f"on page {self.page_index + 1} of this document? "
            "This does not authorize a LoanHub lender or witness role.")
        if answer != QMessageBox.Yes:
            return
        target = Path(self.temp.name) / ("stored_" + uuid.uuid4().hex + ".png")
        try:
            # Create exclusively with owner-only permissions: no plaintext
            # employee signature should be world-readable during PDF assembly.
            fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as signature_file:
                signature_file.write(png)
            del png
            validate_signature_png(target)
            placement = Placement(self.page_index, x, y, width, height, str(target))
            self.signatures.append(placement)
            self.queue_selection_syncing = True
            try:
                self.queue.addItem(f"Page {self.page_index+1} | {width}x{height} pt | {user['display_name']}")
            finally:
                self.queue_selection_syncing = False
            self.position = None
            self.redraw()
        except Exception as exc:
            target.unlink(missing_ok=True)
            QMessageBox.warning(self, "Signature placement failed", str(exc))

    def enroll_local_signature(self):
        """Explicitly enroll or replace the signed-in employee's encrypted signature."""
        user = getattr(self, "local_user", None)
        if not user:
            QMessageBox.warning(self, "Sign in required", "Local employee authentication is required.")
            return
        password, ok = QInputDialog.getText(
            self, "Verify employee", "Enter your local account password:",
            QLineEdit.Password)
        if not ok:
            return
        store = LocalUsers(default_user_db())
        try:
            verified = store.authenticate(user["username"], password)
            if not verified or verified["id"] != user["id"]:
                QMessageBox.warning(self, "Authentication failed", "Incorrect password.")
                return
        finally:
            store.close()
        dialog = CaptureDialog(self.temp.name, self)
        if dialog.exec() != QDialog.Accepted:
            return
        target = Path(self.temp.name) / ("enrollment_" + uuid.uuid4().hex + ".png")
        try:
            dialog.export(target)
            validate_signature_png(target)
            vault = SignatureVault(default_user_db())
            try:
                if vault.has_signature(user["id"]):
                    answer = QMessageBox.question(
                        self, "Replace stored signature",
                        "Replace your existing registered signature?")
                    if answer != QMessageBox.Yes:
                        return
                vault.enroll(user["id"], password, target)
                self.session_signature = target.read_bytes()
            finally:
                vault.close()
            QMessageBox.information(self, "Signature enrolled",
                "Your signature has been stored encrypted for your local account. "
                "It will not be placed on documents automatically.")
        except Exception as exc:
            QMessageBox.warning(self, "Enrollment failed", str(exc))
        finally:
            target.unlink(missing_ok=True)

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
        """Sign directly into IthuteSign's managed library, without a Save As dialog."""
        if not self.signatures:
            QMessageBox.warning(self, "No signatures", "Capture at least one signature first.")
            return
        try:
            if sha256(self.source) != self.source_digest:
                raise ValueError("The source document changed after opening. Reopen it before signing.")
        except Exception as exc:
            QMessageBox.critical(self, "Source changed or unavailable", str(exc))
            return
        answer = QMessageBox.question(
            self, "Confirm signature placement",
            f"Save {len(self.signatures)} signature(s) to IthuteSign's document library?\\n"
            "Review the page positions and sizes before continuing.\\n"
            "The original document will not be overwritten.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            # Generate a temporary signed PDF; the archive makes its own durable copy.
            with tempfile.TemporaryDirectory(prefix="ithutesign_export_") as temporary:
                output = str(Path(temporary) / (Path(self.source).stem + "_signed.pdf"))
                signed_pdf = sign_pdf_many(self.preview_pdf, self.signatures, output,
                                           source_document=self.source)
                ids = extract_national_ids(signed_pdf)
                if len(ids) == 1:
                    national_id = ids[0]
                    confirmation = QMessageBox.question(
                        self, "Confirm client National ID",
                        "File this signed document under National ID: " + national_id + "?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if confirmation != QMessageBox.Yes:
                        return
                else:
                    explanation = ("Multiple National IDs were found." if ids else
                                   "No labelled National ID was detected.")
                    entered, accepted = QInputDialog.getText(
                        self, "Client National ID",
                        explanation + "\\nEnter the CLIENT'S National ID from the contract:")
                    if not accepted:
                        return
                    national_id = normalize_national_id(entered)
                archived_pdf = archive_signed_pdf(signed_pdf, national_id=national_id)
            self.last_signed_pdf = str(archived_pdf)
            self.last_signed_pdf_digest = sha256(archived_pdf)
            self.last_signed_source = self.source
            QMessageBox.information(
                self, "Saved to IthuteSign",
                "Signed PDF saved in IthuteSign's document library.\\n"
                "Use 'Signed document library' to reopen or email it.")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def open_signed_library(self):
        """Open the full-screen client document explorer."""
        from library_dialog import SignedLibraryDialog
        dialog = SignedLibraryDialog(self.load_document, self)
        dialog.showFullScreen()
        dialog.exec()

    def send_signed_imail(self):
        if not self.last_signed_pdf or not Path(self.last_signed_pdf).is_file():
            QMessageBox.warning(self, "iMail", "Save a signed PDF before emailing.")
            return
        if self.last_signed_source != self.source:
            QMessageBox.warning(self, "iMail", "The signed PDF belongs to another document.")
            return
        try:
            if sha256(self.last_signed_pdf) != self.last_signed_pdf_digest:
                raise ValueError("Signed PDF changed after saving. Sign and save again.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "iMail", str(exc))
            return
        IMailDeliveryDialog(self.last_signed_pdf, self).exec()

    def send_signed_whatsapp(self):
        if not self.last_signed_pdf or not Path(self.last_signed_pdf).is_file():
            QMessageBox.warning(self, "WhatsApp", "Save a signed PDF before sending.")
            return
        if self.last_signed_source != self.source:
            QMessageBox.warning(self, "WhatsApp", "The signed PDF belongs to another document. Save this document first.")
            return
        try:
            if sha256(self.last_signed_pdf) != self.last_signed_pdf_digest:
                raise ValueError("Signed PDF has changed since saving. Reopen and sign again.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "WhatsApp", str(exc))
            return
        WhatsAppDeliveryDialog(self.loanhub_access_token, self.loanhub_company,
                               self.last_signed_pdf, self).exec()

    def closeEvent(self, event):
        self.logout_loanhub()
        self.session_signature = None
        if self.doc is not None:
            self.doc.close()
        self.temp.cleanup()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    login = LocalLoginDialog()
    if login.exec() != QDialog.Accepted:
        sys.exit(0)
    window = Window()
    window.local_user = login.user
    window.session_signature = login.unlocked_signature
    login.unlocked_signature = None
    window.show()
    # Explicit --open prevents accidental interpretation of Qt or other flags as paths.
    if len(sys.argv) == 3 and sys.argv[1] == "--open":
        window.load_document(sys.argv[2])
    sys.exit(app.exec())
