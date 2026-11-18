"""Offscreen regression checks for IthuteSign's signed-document explorer."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import fitz
import pytest
from PySide6.QtWidgets import QApplication, QTreeWidget, QListWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from signed_library import archive_signed_pdf
from library_dialog import SignedLibraryDialog


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    # Release Qt-owned clipboard MIME data while QApplication is still alive.\n    # Otherwise some PySide6/Linux versions crash during interpreter shutdown.\n    from PySide6.QtGui import QGuiApplication\n    QGuiApplication.clipboard().clear()\n

@pytest.fixture
def explorer(tmp_path, monkeypatch, app):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "archive"))
    for name, pages in (("Agreement.pdf", 2), ("Schedule.pdf", 1)):
        source = tmp_path / name
        with fitz.open() as pdf:
            for _ in range(pages):
                pdf.new_page()
            pdf.save(source)
        archive_signed_pdf(source, national_id="123456789012")
    dialog = SignedLibraryDialog(lambda _: None)
    yield dialog
    dialog.close()


def test_folder_navigation_and_details_columns(explorer):
    assert isinstance(explorer.lists[0], QTreeWidget)
    assert isinstance(explorer.lists[1], QListWidget)
    assert explorer.lists[0].columnCount() == 5
    explorer.navigate("123456789012")
    assert explorer.lists[0].topLevelItemCount() == 2
    assert explorer.lists[1].count() == 2


def test_selection_survives_sort_and_view_switch(explorer):
    explorer.navigate("123456789012")
    details = explorer.lists[0]
    details.setCurrentItem(details.topLevelItem(0))
    selected = explorer.current_record()
    explorer.sort_by_column(0)
    assert explorer.current_record() == selected
    explorer.set_mode(1)
    assert explorer.current_record() == selected
    explorer.set_mode(0)
    assert explorer.current_record() == selected


def test_pdf_preview_and_properties(explorer, monkeypatch):
    explorer.navigate("123456789012")
    details = explorer.lists[0]
    details.setCurrentItem(details.topLevelItem(0))
    assert explorer.preview.path is not None
    assert explorer.preview.total >= 1
    assert explorer.preview.zoom_mode == "page"
    explorer.preview.set_zoom_mode("width")
    assert explorer.preview.zoom_mode == "width"
    explorer.preview.adjust_zoom(25)
    assert explorer.preview.zoom_mode == "custom"
    captured = []
    monkeypatch.setattr("library_dialog.QMessageBox.information",
                        lambda *args: captured.append(args[2]))
    explorer.show_properties()
    assert captured and "Integrity: Verified" in captured[0]


def test_download_via_dialog_preserves_original(explorer, tmp_path, monkeypatch):
    explorer.navigate("123456789012")
    explorer.lists[0].setCurrentItem(explorer.lists[0].topLevelItem(0))
    source = explorer.selected_pdf()
    destination = tmp_path / "exported.pdf"
    monkeypatch.setattr("library_dialog.QFileDialog.getSaveFileName",
                        lambda *args: (str(destination), "PDF documents (*.pdf)"))
    monkeypatch.setattr("library_dialog.QMessageBox.information", lambda *args: None)
    explorer.download_selected()
    assert destination.read_bytes() == source.read_bytes()
    assert source.is_file()


def test_copy_pdf_to_os_clipboard_uses_staged_copy(explorer):
    from PySide6.QtGui import QGuiApplication
    explorer.navigate("123456789012")
    explorer.lists[0].setCurrentItem(explorer.lists[0].topLevelItem(0))
    original = explorer.selected_pdf()
    explorer.copy_selected()
    mime = QGuiApplication.clipboard().mimeData()
    assert mime.hasUrls()
    assert len(mime.urls()) == 1
    copied = Path(mime.urls()[0].toLocalFile())
    assert copied != original
    assert copied.read_bytes() == original.read_bytes()
    assert copied.parent.name.startswith("ithutesign-copy-")
    assert b"copy" in bytes(mime.data("x-special/gnome-copied-files"))
    assert original.is_file()


def test_tampered_pdf_cannot_be_copied(explorer, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    explorer.navigate("123456789012")
    explorer.lists[0].setCurrentItem(explorer.lists[0].topLevelItem(0))
    original = explorer.selected_pdf()
    original.write_bytes(b"tampered")
    warnings = []
    monkeypatch.setattr("library_dialog.QMessageBox.critical",
                        lambda *args: warnings.append(args[2]))
    explorer.copy_selected()
    assert warnings
