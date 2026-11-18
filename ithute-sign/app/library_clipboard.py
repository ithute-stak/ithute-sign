"""Copy verified signed PDFs to the OS file clipboard without exposing archive paths."""
import atexit
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QGuiApplication

from library_export import export_archived_pdf

_clipboard_staging = []


def copy_archived_pdf_to_clipboard(record, source):
    """Stage a verified, read-only-independent copy for paste into file managers."""
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        raise RuntimeError("System clipboard unavailable")
    temporary = tempfile.TemporaryDirectory(prefix="ithutesign-copy-")
    try:
        directory = Path(temporary.name)
        os.chmod(directory, 0o700)
        name = Path(str(record.get("name") or "signed-document.pdf")).name
        if name in ("", ".", "..") or not name.lower().endswith(".pdf"):
            name = "signed-document.pdf"
        staged = export_archived_pdf(record, source, directory / name)
        os.chmod(staged, 0o600)
        url = QUrl.fromLocalFile(str(staged))
        mime = QMimeData()
        mime.setUrls([url])
        # GNOME/Nautilus recognizes this as COPY, never MOVE.
        mime.setData("x-special/gnome-copied-files", ("copy\\n" + url.toString()).encode("utf-8"))
        clipboard.setMimeData(mime)
        # Retain the staged file for the application lifetime, including subsequent copies.
        _clipboard_staging.append(temporary)
        atexit.register(temporary.cleanup)
        return staged
    except BaseException:
        temporary.cleanup()
        raise
