"""Full-screen, Explorer-inspired client document library."""
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem, QSplitter,
    QWidget, QStackedWidget, QMessageBox, QStyle, QAbstractItemView, QFileDialog, QComboBox, QHeaderView, QMenu,
)

from signed_library import list_signed_pdfs, verify_archived_pdf
from imail_dialog import IMailDeliveryDialog
from pdf_preview import PdfPreview
from library_export import export_archived_pdf


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
        self.history = [None]
        self.history_index = 0
        self._navigating = False
        self.pdf_file_icon = pdf_icon()
        self.folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        self.setWindowTitle("IthuteSign | Client Document Explorer")
        self.setMinimumSize(850, 550)
        self.setStyleSheet("""
            QDialog { background: #edf3f9; color: #152b46; }
            QLabel { color: #152b46; background: transparent; }
            QLabel#header { color: #102943; font-size: 25px; font-weight: 800; }
            QTreeWidget, QListWidget { background: #ffffff; color: #20364e;
                border: 1px solid #cddae8; border-radius: 10px; padding: 9px;
                font-size: 13px; }
            QTreeWidget::item, QListWidget::item { padding: 9px; border-radius: 5px; }
            QTreeWidget::item:hover, QListWidget::item:hover { background: #edf5ff; }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background: #cde6fc; color: #0b3153; }
            QHeaderView::section { background: #e0ebf6; color: #1b3551;
                padding: 10px; border: none; font-weight: bold; }
            QLineEdit { background: white; color: #142b46; padding: 12px;
                border: 1px solid #bacde0; border-radius: 9px; font-size: 13px; }
            QLineEdit:focus { border: 2px solid #168a9b; }
            QPushButton { padding: 10px 16px; background: #ffffff; color: #17334f;
                border: 1px solid #c5d5e5; border-radius: 8px; font-weight: 650; }
            QPushButton:hover { background: #e2f2fc; border-color: #75b5d5; }
            QPushButton:disabled { color: #8ca0b3; background: #edf1f5; }
            QPushButton#downloadButton { background: #087f88; color: #ffffff;
                border: 1px solid #087f88; font-weight: 750; }
            QPushButton#downloadButton:hover { background: #06676e; }
            QSplitter::handle { background: #dce6ef; width: 5px; }
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
        navigation = QHBoxLayout()
        self.back_button = QPushButton("← Back")
        self.home_button = QPushButton("⌂ Home")
        self.up_button = QPushButton("↑ Up")
        for button in (self.back_button, self.home_button, self.up_button):
            navigation.addWidget(button)
        navigation.addStretch()
        root.addLayout(navigation)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search National ID, client folders, filenames or dates...")
        self.search.setClearButtonEnabled(True)
        tools.addWidget(self.search, 1)
        self.sort_choice = QComboBox()
        self.sort_choice.addItems(["Newest first", "Oldest first", "Name A-Z", "Name Z-A", "Largest first", "Smallest first"])
        self.sort_choice.setStyleSheet("QComboBox { background: white; color: #17334f; padding: 9px; border: 1px solid #c5d5e5; }")
        tools.addWidget(self.sort_choice)
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
        details = QTreeWidget()
        details.setHeaderLabels(["Name", "Client National ID", "Date saved", "Type", "Size"])
        details.setRootIsDecorated(False)
        details.setAlternatingRowColors(True)
        details.setSelectionMode(QAbstractItemView.SingleSelection)
        details.setIconSize(QSize(24, 24))
        details.header().setSectionResizeMode(QHeaderView.Interactive)
        details.header().setStretchLastSection(False)
        for column, width in enumerate((245, 155, 145, 70, 90)):
            details.setColumnWidth(column, width)
        details.header().sectionClicked.connect(self.sort_by_column)
        details.itemDoubleClicked.connect(self.activate_item)
        details.currentItemChanged.connect(self.preview_selection)
        self.lists.append(details)
        self.views.addWidget(details)
        tiles = QListWidget()
        tiles.setViewMode(QListWidget.IconMode)
        tiles.setSelectionMode(QAbstractItemView.SingleSelection)
        tiles.setIconSize(QSize(42, 42))
        tiles.setGridSize(QSize(185, 125))
        tiles.setWordWrap(True)
        tiles.setResizeMode(QListWidget.Adjust)
        tiles.setMovement(QListWidget.Static)
        tiles.setSpacing(10)
        tiles.itemDoubleClicked.connect(self.activate_item)
        tiles.currentItemChanged.connect(self.preview_selection)
        self.lists.append(tiles)
        self.views.addWidget(tiles)
        for view in self.lists:
            view.setContextMenuPolicy(Qt.CustomContextMenu)
            view.customContextMenuRequested.connect(
                lambda pos, source=view: self.show_document_menu(source, pos))
        panel_layout.addWidget(self.views)
        splitter.addWidget(panel)
        self.preview = PdfPreview()
        self.preview.setStyleSheet("QLabel { color: #17334f; background: transparent; }")
        self.preview.setMinimumWidth(260)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([230, 640, 470])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.status = QLabel()
        footer.addWidget(self.status, 1)
        self.open_button = QPushButton("Open PDF")
        self.download_button = QPushButton("↓ Download PDF")
        self.download_button.setObjectName("downloadButton")
        self.email_button = QPushButton("Email via iMail")
        self.close_button = QPushButton("Close")
        footer.addWidget(self.open_button)
        footer.addWidget(self.download_button)
        footer.addWidget(self.email_button)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

        self.back_button.clicked.connect(self.go_back)
        self.home_button.clicked.connect(lambda: self.navigate(None))
        self.up_button.clicked.connect(lambda: self.navigate(None))
        self.search.textChanged.connect(self.refresh)
        self.sort_choice.currentIndexChanged.connect(self.refresh)
        self.folders.currentItemChanged.connect(self.folder_changed)
        self.list_button.clicked.connect(lambda: self.set_mode(0))
        self.tile_button.clicked.connect(lambda: self.set_mode(1))
        self.open_button.clicked.connect(self.open_selected)
        self.download_button.clicked.connect(self.download_selected)
        self.email_button.clicked.connect(self.email_selected)
        self.close_button.clicked.connect(self.reject)
        self.shortcuts = []
        for key, action in (("Ctrl+F", self.search.setFocus),
                            ("Ctrl+S", self.download_selected),
                            ("Ctrl+O", self.open_selected),
                            ("Alt+Left", self.go_back),
                            ("Alt+Up", lambda: self.navigate(None)),
                            ("F5", self.refresh)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)
        self.refresh()
        self.navigate(None, record_history=False)

    def sort_by_column(self, column):
        """Keep both views in the same ordering after a header click."""
        mapping = {0: (2, 3), 1: (2, 3), 2: (0, 1), 4: (4, 5)}
        if column not in mapping:
            return
        ascending, descending = mapping[column]
        current = self.sort_choice.currentIndex()
        self.sort_choice.setCurrentIndex(descending if current == ascending else ascending)

    def show_document_menu(self, view, pos):
        """Actions operate on the item under the pointer, not stale selection."""
        item = view.itemAt(pos)
        if item is None:
            return
        view.setCurrentItem(item)
        key = self.item_key(item)
        menu = QMenu(self)
        if isinstance(key, str) and key.startswith("folder:"):
            action = menu.addAction("Open folder")
            action.triggered.connect(lambda: self.navigate(key[7:]))
        else:
            menu.addAction("Open PDF", self.open_selected)
            menu.addAction("Download a copy…", self.download_selected)
            menu.addAction("Email via iMail", self.email_selected)
        menu.exec(view.viewport().mapToGlobal(pos))

    def folder_changed(self, current, previous):
        if not self._navigating:
            self.navigate(current.data(0, Qt.UserRole) if current else None)

    def navigate(self, folder, record_history=True):
        if folder is not None and folder not in self.groups:
            return
        if record_history and folder != self.active_folder:
            self.history = self.history[:self.history_index + 1]
            self.history.append(folder)
            self.history_index += 1
        self.active_folder = folder
        self._navigating = True
        try:
            for index in range(self.folders.topLevelItemCount()):
                item = self.folders.topLevelItem(index)
                if item.data(0, Qt.UserRole) == folder:
                    self.folders.setCurrentItem(item)
                    break
        finally:
            self._navigating = False
        self.breadcrumb.setText("IthuteSign  /  " + (folder or "Client folders"))
        self.back_button.setEnabled(self.history_index > 0)
        self.up_button.setEnabled(folder is not None)
        self.refresh()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.navigate(self.history[self.history_index], record_history=False)

    def activate_item(self, item):
        value = self.item_key(item)
        if isinstance(value, str) and value.startswith("folder:"):
            self.navigate(value[7:])
        else:
            self.open_selected()

    @staticmethod
    def item_key(item):
        if item is None:
            return None
        if isinstance(item, QTreeWidgetItem):
            return item.data(0, Qt.UserRole)
        return item.data(Qt.UserRole)

    def set_mode(self, index):
        old = self.current_record()
        self.views.setCurrentIndex(index)
        self.preview.clear()
        if old is not None:
            widget = self.lists[index]
            items = (widget.topLevelItem(i) for i in range(widget.topLevelItemCount())) if index == 0 else (
                widget.item(i) for i in range(widget.count()))
            for item in items:
                if self.item_key(item) == old:
                    widget.setCurrentItem(item)
                    break

    def refresh(self, *_):
        query = self.search.text().casefold().strip()
        folders = []
        shown = []
        if self.active_folder is None:
            for folder, documents in sorted(self.groups.items()):
                if not query or query in folder.casefold() or any(
                    query in str(record.get("name", "")).casefold()
                    or query in str(record.get("created_at", "")).casefold()
                    for record, _ in documents
                ):
                    folders.append((folder, len(documents)))
        for record, path in self.entries:
            folder = record.get("national_id") or "Legacy / unassigned"
            if self.active_folder is None and not query:
                continue
            if self.active_folder is not None and folder != self.active_folder:
                continue
            haystack = " ".join((folder, record.get("name", ""), record.get("created_at", ""))).casefold()
            if query and query not in haystack:
                continue
            shown.append((record, path))
        sort_index = self.sort_choice.currentIndex()
        if sort_index in (0, 1):
            shown.sort(key=lambda pair: str(pair[0].get("created_at", "")), reverse=sort_index == 0)
        elif sort_index in (2, 3):
            shown.sort(key=lambda pair: str(pair[0].get("name", "")).casefold(), reverse=sort_index == 3)
        else:
            shown.sort(key=lambda pair: pair[1].stat().st_size if pair[1].exists() else 0,
                       reverse=sort_index == 4)
        for widget in self.lists:
            widget.clear()
            is_details = isinstance(widget, QTreeWidget)
            for folder, count in folders:
                if is_details:
                    item = QTreeWidgetItem([folder, "", "", "Folder", f"{count} files"])
                    item.setIcon(0, self.folder_icon)
                    item.setData(0, Qt.UserRole, "folder:" + folder)
                    widget.addTopLevelItem(item)
                else:
                    item = QListWidgetItem(self.folder_icon, f"{folder}\\n{count} documents")
                    item.setData(Qt.UserRole, "folder:" + folder)
                    widget.addItem(item)
            for record, path in shown:
                folder = record.get("national_id") or "Legacy / unassigned"
                date = record.get("created_at", "")[:16].replace("T", " ")
                try:
                    size_kb = (path.stat().st_size + 1023) // 1024
                except OSError:
                    size_kb = 0
                name = record.get("name", "Document")
                if is_details:
                    item = QTreeWidgetItem([name, folder, date, "PDF", f"{size_kb} KB"])
                    item.setIcon(0, self.pdf_file_icon)
                    item.setData(0, Qt.UserRole, record["id"])
                    item.setToolTip(0, name)
                    widget.addTopLevelItem(item)
                else:
                    item = QListWidgetItem(self.pdf_file_icon, name + "\\n" + folder)
                    item.setData(Qt.UserRole, record["id"])
                    item.setToolTip(f"Client: {folder}\\nSaved: {date}\\nSize: {size_kb} KB")
                    widget.addItem(item)
        self.count.setText(f"{len(self.groups)} client folders  •  {len(self.entries)} documents")
        self.status.setText(f"{len(folders)} folders  •  {len(shown)} documents shown")
        self.preview.clear()

    def preview_selection(self, current, previous):
        if self.views.currentWidget() not in self.lists:
            return
        if not current:
            self.preview.clear()
            return
        entry_id = self.item_key(current)
        if not entry_id or entry_id.startswith("folder:"):
            self.preview.clear("Open a client folder to select a PDF")
            return
        for record, path in self.entries:
            if record["id"] == entry_id:
                try:
                    verified = verify_archived_pdf(record, path)
                    self.preview.load_pdf(verified, record)
                except (OSError, ValueError):
                    self.preview.clear("Document integrity verification failed")
                return
        self.preview.clear("Document unavailable")

    def current_record(self):
        item = self.lists[self.views.currentIndex()].currentItem()
        return self.item_key(item)

    def selected_pdf(self):
        record_id = self.current_record()
        if record_id and record_id.startswith("folder:"):
            self.navigate(record_id[7:])
            return None
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

    def download_selected(self):
        """Save a verified copy to a user-selected location, never move the archive."""
        pdf = self.selected_pdf()
        if not pdf:
            return
        record = next((r for r, p in self.entries if r["id"] == self.current_record()), None)
        if record is None:
            return
        suggested_name = Path(record.get("name") or "signed-document.pdf").name
        if not suggested_name.lower().endswith(".pdf"):
            suggested_name += ".pdf"
        default = str(Path.home() / "Downloads" / suggested_name)
        destination, _ = QFileDialog.getSaveFileName(
            self, "Download a copy of the signed PDF", default, "PDF documents (*.pdf)")
        if not destination:
            return
        if not destination.lower().endswith(".pdf"):
            destination += ".pdf"
        target = Path(destination)
        if target.exists():
            QMessageBox.warning(
                self, "File already exists",
                "Choose another filename. IthuteSign will not overwrite an existing PDF.")
            return
        try:
            saved = export_archived_pdf(record, pdf, target)
            QMessageBox.information(self, "PDF downloaded",
                                    "A copy was saved to:\\n" + str(saved) +
                                    "\\n\\nThe IthuteSign original remains unchanged.")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Download failed", str(exc))
