"""Full-screen, Explorer-inspired client document library."""
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem, QSplitter,
    QWidget, QStackedWidget, QMessageBox, QStyle, QAbstractItemView,
)

from signed_library import list_signed_pdfs, verify_archived_pdf
from imail_dialog import IMailDeliveryDialog


def pdf_icon(size=64):
    """Draw a crisp PDF document icon without relying on desktop icon themes."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    scale = size / 64
    painter.scale(scale, scale)
    painter.setPen(QPen(QColor("#b7c7d8"), 1.5))
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(12, 4, 40, 54, 4, 4)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#d73540"))
    painter.drawRoundedRect(6, 31, 52, 23, 4, 4)
    painter.setPen(QColor("#ffffff"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(16)
    painter.setFont(font)
    painter.drawText(6, 31, 52, 23, Qt.AlignCenter, "PDF")
    painter.end()
    return QIcon(pixmap)


class SignedLibraryDialog(QDialog):
    """Browse National-ID folders; list and tile modes share one filtered model."""

    def __init__(self, open_document, parent=None):
        super().__init__(parent)
        self.open_document = open_document
        self.entries = list_signed_pdfs()
        self.groups = defaultdict(list)
        for record, path in self.entries:
            self.groups[record.get("national_id") or "Legacy / unassigned"].append((record, path))
        self.active_folder = None
        self.pdf_file_icon = pdf_icon()
        self.folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        self.setWindowTitle("IthuteSign | Client Document Explorer")
        self.setMinimumSize(850, 550)
        self.setStyleSheet("""
            QDialog { background: #f4f7fb; color: #172d46; }
            QTreeWidget, QListWidget { background: white; color: #172d46;
                border: 1px solid #d7e0eb; border-radius: 7px; padding: 8px; }
            QTreeWidget::item, QListWidget::item { padding: 7px; }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background: #d8eaf9; color: #102d48; }
            QLineEdit { background: white; color: #172d46; padding: 11px;
                border: 1px solid #cbd8e6; border-radius: 7px; }
            QPushButton { padding: 10px 14px; background: white; color: #18304c;
                border: 1px solid #cbd8e6; border-radius: 7px; }
            QPushButton:hover { background: #e6f2fb; }
            QLabel#header { font-size: 23px; font-weight: 750; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Client Document Explorer")
        title.setObjectName("header")
        header.addWidget(title)
        header.addStretch()
        self.count = QLabel()
        header.addWidget(self.count)
        root.addLayout(header)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search National ID, client folders, filenames or dates...")
        self.search.setClearButtonEnabled(True)
        tools.addWidget(self.search, 1)
        self.list_button = QPushButton("☰  List")
        self.tile_button = QPushButton("▦  Tiles")
        tools.addWidget(self.list_button)
        tools.addWidget(self.tile_button)
        root.addLayout(tools)

        splitter = QSplitter(Qt.Horizontal)
        self.folders = QTreeWidget()
        self.folders.setHeaderLabel("CLIENT FOLDERS")
        self.folders.setMinimumWidth(210)
        self.folders.setMaximumWidth(390)
        self.folders.setRootIsDecorated(False)
        self.folders.setSelectionMode(QAbstractItemView.SingleSelection)
        all_item = QTreeWidgetItem(["All documents"])
        all_item.setData(0, Qt.UserRole, None)
        all_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirHomeIcon))
        self.folders.addTopLevelItem(all_item)
        self.folders.setCurrentItem(all_item)
        for national_id in sorted(self.groups):
            item = QTreeWidgetItem([national_id + "  (" + str(len(self.groups[national_id])) + ")"])
            item.setData(0, Qt.UserRole, national_id)
            item.setIcon(0, self.folder_icon)
            self.folders.addTopLevelItem(item)
        splitter.addWidget(self.folders)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 0, 0, 0)
        self.breadcrumb = QLabel("IthuteSign  /  All documents")
        panel_layout.addWidget(self.breadcrumb)
        self.views = QStackedWidget()
        self.lists = []
        for mode in (QListWidget.ListMode, QListWidget.IconMode):
            widget = QListWidget()
            widget.setViewMode(mode)
            widget.setSelectionMode(QAbstractItemView.SingleSelection)
            widget.setIconSize(QSize(42, 42) if mode == QListWidget.IconMode else QSize(23, 23))
            if mode == QListWidget.IconMode:
                widget.setGridSize(QSize(185, 125))
                widget.setWordWrap(True)
                widget.setResizeMode(QListWidget.Adjust)
                widget.setMovement(QListWidget.Static)
                widget.setSpacing(10)
            widget.itemDoubleClicked.connect(self.open_selected)
            self.lists.append(widget)
            self.views.addWidget(widget)
        panel_layout.addWidget(self.views)
        splitter.addWidget(panel)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.status = QLabel()
        footer.addWidget(self.status, 1)
        self.open_button = QPushButton("Open PDF")
        self.email_button = QPushButton("Email via iMail")
        self.close_button = QPushButton("Close")
        footer.addWidget(self.open_button)
        footer.addWidget(self.email_button)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

        self.search.textChanged.connect(self.refresh)
        self.folders.currentItemChanged.connect(self.folder_changed)
        self.list_button.clicked.connect(lambda: self.set_mode(0))
        self.tile_button.clicked.connect(lambda: self.set_mode(1))
        self.open_button.clicked.connect(self.open_selected)
        self.email_button.clicked.connect(self.email_selected)
        self.close_button.clicked.connect(self.reject)
        self.refresh()

    def folder_changed(self, current, previous):
        self.active_folder = current.data(0, Qt.UserRole) if current else None
        self.breadcrumb.setText("IthuteSign  /  " + (self.active_folder or "All documents"))
        self.refresh()

    def set_mode(self, index):
        old = self.current_record()
        self.views.setCurrentIndex(index)
        if old is not None:
            for i in range(self.lists[index].count()):
                if self.lists[index].item(i).data(Qt.UserRole) == old:
                    self.lists[index].setCurrentRow(i)
                    break

    def refresh(self, *_):
        query = self.search.text().casefold().strip()
        shown = []
        for record, path in self.entries:
            folder = record.get("national_id") or "Legacy / unassigned"
            if self.active_folder is not None and folder != self.active_folder:
                continue
            haystack = " ".join((folder, record.get("name", ""), record.get("created_at", ""))).casefold()
            if query and query not in haystack:
                continue
            shown.append((record, path))
        for widget in self.lists:
            widget.clear()
            for record, path in shown:
                folder = record.get("national_id") or "Legacy / unassigned"
                date = record.get("created_at", "")[:16].replace("T", " ")
                if widget.viewMode() == QListWidget.IconMode:
                    label = record.get("name", "Document") + "\n" + folder
                else:
                    label = record.get("name", "Document") + "     |     " + folder + "     |     " + date
                item = QListWidgetItem(
                    self.pdf_file_icon, label)
                item.setData(Qt.UserRole, record["id"])
                item.setToolTip(f"Client: {folder}\nDocument: {record.get('name')}\nSaved: {date}")
                widget.addItem(item)
        self.count.setText(f"{len(self.groups)} client folders  •  {len(self.entries)} documents")
        self.status.setText(f"{len(shown)} documents shown")

    def current_record(self):
        item = self.lists[self.views.currentIndex()].currentItem()
        return item.data(Qt.UserRole) if item else None

    def selected_pdf(self):
        record_id = self.current_record()
        if not record_id:
            QMessageBox.warning(self, "Select document", "Select a saved PDF first.")
            return None
        for record, path in self.entries:
            if record["id"] == record_id:
                try:
                    return verify_archived_pdf(record, path)
                except (OSError, ValueError) as exc:
                    QMessageBox.critical(self, "Document integrity error", str(exc))
                    return None
        QMessageBox.warning(self, "Document unavailable", "This document is no longer available.")
        return None

    def open_selected(self, *_):
        pdf = self.selected_pdf()
        if pdf:
            self.accept()
            self.open_document(str(pdf))

    def email_selected(self):
        pdf = self.selected_pdf()
        if pdf:
            IMailDeliveryDialog(str(pdf), self).exec()
