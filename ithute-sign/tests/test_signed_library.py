import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from signed_library import archive_signed_pdf, list_signed_pdfs, verify_archived_pdf


def test_archive_persists_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "signed.pdf"
    source.write_bytes(b"%PDF-1.7\n" + b"sample signed PDF" * 20)
    archived = archive_signed_pdf(source, national_id='123456789012')
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
    archived = archive_signed_pdf(source, national_id='123456789012')
    record, path = list_signed_pdfs()[0]
    archived.write_bytes(b"%PDF-1.7\n" + b"modified")
    with pytest.raises(ValueError, match="integrity"):
        verify_archived_pdf(record, path)


def test_archive_rejects_non_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "fake.pdf"
    source.write_text("not a PDF")
    with pytest.raises(ValueError):
        archive_signed_pdf(source, national_id='123456789012')


def test_same_client_documents_share_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "signed.pdf"
    source.write_bytes(b"%PDF-1.7\\n" + b"sample" * 30)
    first = archive_signed_pdf(source, national_id="123456789012")
    second = archive_signed_pdf(source, national_id="123456789012")
    assert first.parent == second.parent
    assert first != second
    assert len(list_signed_pdfs()) == 2


def test_reject_unsafe_national_id(tmp_path, monkeypatch):
    monkeypatch.setenv("ITHUTESIGN_LIBRARY_DIR", str(tmp_path / "library"))
    source = tmp_path / "signed.pdf"
    source.write_bytes(b"%PDF-1.7\\n" + b"sample" * 30)
    with pytest.raises(ValueError):
        archive_signed_pdf(source, national_id="../other")
