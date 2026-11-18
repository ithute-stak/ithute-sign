import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from signed_library import archive_signed_pdf, list_signed_pdfs, verify_archived_pdf


def test_archive_persists_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "signed.pdf"
    source.write_bytes(b"%PDF-1.7\n" + b"sample signed PDF" * 20)
    archived = archive_signed_pdf(source)
    assert archived.is_file()
    assert archived != source
    entries = list_signed_pdfs()
    assert len(entries) == 1
    assert entries[0][0]["name"] == "signed.pdf"
    assert verify_archived_pdf(*entries[0]) == archived


def test_archive_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "signed.pdf"
    source.write_bytes(b"%PDF-1.7\n" + b"example" * 20)
    archived = archive_signed_pdf(source)
    record, path = list_signed_pdfs()[0]
    archived.write_bytes(b"%PDF-1.7\n" + b"modified")
    with pytest.raises(ValueError, match="integrity"):
        verify_archived_pdf(record, path)


def test_archive_rejects_non_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "fake.pdf"
    source.write_text("not a PDF")
    with pytest.raises(ValueError):
        archive_signed_pdf(source)
