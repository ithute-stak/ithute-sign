"""Verified PDF export tests."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from signed_library import archive_signed_pdf, list_signed_pdfs
from library_export import export_archived_pdf


def test_export_preserves_archive(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "contract.pdf"
    data = b"%PDF-1.7\n" + b"test" * 100
    source.write_bytes(data)
    archived = archive_signed_pdf(source, national_id="123456789012")
    record, path = list_signed_pdfs()[0]
    exported = export_archived_pdf(record, path, tmp_path / "download.pdf")
    assert exported.read_bytes() == data
    assert archived.read_bytes() == data


def test_export_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "contract.pdf"
    source.write_bytes(b"%PDF-1.7\n" + b"test" * 100)
    archive_signed_pdf(source, national_id="123456789012")
    record, path = list_signed_pdfs()[0]
    destination = tmp_path / "download.pdf"
    destination.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        export_archived_pdf(record, path, destination)
    assert destination.read_bytes() == b"existing"


def test_export_rejects_tampered_archive(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "contract.pdf"
    source.write_bytes(b"%PDF-1.7\n" + b"test" * 100)
    archived = archive_signed_pdf(source, national_id="123456789012")
    record, path = list_signed_pdfs()[0]
    archived.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        export_archived_pdf(record, path, tmp_path / "download.pdf")


def test_exclusive_create_race_never_deletes_other_file(tmp_path, monkeypatch):
    """Another writer wins between existence check and exclusive creation."""
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "contract.pdf"
    source.write_bytes(b"%PDF-1.7\\n" + b"test" * 100)
    archive_signed_pdf(source, national_id="123456789012")
    record, path = list_signed_pdfs()[0]
    destination = tmp_path / "race.pdf"
    original_open = Path.open

    def racing_open(self, mode="r", *args, **kwargs):
        if self == destination and mode == "xb":
            destination.write_bytes(b"another writer's document")
            raise FileExistsError("Created by another process")
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)
    with pytest.raises(FileExistsError):
        export_archived_pdf(record, path, destination)
    assert destination.read_bytes() == b"another writer's document"
