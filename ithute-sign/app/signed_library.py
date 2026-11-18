"""Private local archive for signed PDF documents. No cloud upload."""
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from document import sha256


def library_root():
    override = os.environ.get("ITHUTESIGN_LIBRARY_DIR")
    return Path(override).expanduser() if override else Path.home() / ".local" / "share" / "IthuteSign" / "signed-documents"


def archive_signed_pdf(source):
    source = Path(source)
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("Signed PDF is missing")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Not a PDF")
    root = library_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    entry_id = uuid.uuid4().hex
    destination = root / (entry_id + ".pdf")
    metadata = root / (entry_id + ".json")
    try:
        with source.open("rb") as src, destination.open("xb") as dst:
            os.chmod(destination, 0o600)
            shutil.copyfileobj(src, dst)
        record = {
            "id": entry_id,
            "name": source.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sha256": sha256(destination),
        }
        with metadata.open("x", encoding="utf-8") as handle:
            os.chmod(metadata, 0o600)
            json.dump(record, handle)
    except Exception:
        destination.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)
        raise
    return destination


def list_signed_pdfs():
    root = library_root()
    if not root.exists():
        return []
    records = []
    for metadata in root.glob("*.json"):
        try:
            record = json.loads(metadata.read_text(encoding="utf-8"))
            if record["id"] != metadata.stem or len(record["id"]) != 32:
                continue
            pdf = root / (record["id"] + ".pdf")
            if pdf.is_file():
                records.append((record, pdf))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(records, key=lambda item: item[0]["created_at"], reverse=True)


def verify_archived_pdf(record, path):
    path = Path(path).resolve()
    if path.parent != library_root().resolve() or path.name != record["id"] + ".pdf":
        raise ValueError("Document is outside the signed archive")
    if sha256(path) != record["sha256"]:
        raise ValueError("Archived PDF integrity check failed")
    return path
