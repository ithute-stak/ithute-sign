"""Private local archive, grouped by verified client National ID."""
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz
from document import sha256

ID_LABEL = re.compile(r"(?i)\\b(?:national\\s*(?:id|identity)(?:\\s*(?:number|no\\.?))?|identity\\s*(?:number|no\\.?)|id\\s*(?:number|no\\.?))\\s*[:#-]?\\s*([A-Za-z0-9][A-Za-z0-9 /-]{4,28})")
ID_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{4,31}\\Z")


def library_root():
    override = os.environ.get("ITHUTESIGN_LIBRARY_DIR")
    return Path(override).expanduser() if override else Path.home() / ".local" / "share" / "IthuteSign" / "signed-documents"


def normalize_national_id(value):
    value = re.sub(r"\\s+", "", value.strip()).upper()
    if not ID_SAFE.fullmatch(value) or value in {"UNKNOWN", "NOTAVAILABLE"}:
        raise ValueError("Enter a valid National ID (letters, digits or hyphens)")
    return value


def extract_national_ids(pdf_path):
    """Extract only explicitly labelled National IDs; never infer from random numbers."""
    found = set()
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            for line in page.get_text("text").splitlines():
                for match in ID_LABEL.finditer(line):
                    candidate = match.group(1).strip().split("  ")[0].strip(" -/")
                    # Keep first whitespace-delimited token unless the ID itself has spaces.
                    candidate = candidate.split()[0]
                    try:
                        found.add(normalize_national_id(candidate))
                    except ValueError:
                        pass
    return sorted(found)


def archive_signed_pdf(source, national_id=None):
    source = Path(source)
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("Signed PDF is missing")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Not a PDF")
    candidates = extract_national_ids(source) if national_id is None else []
    if national_id is None:
        if len(candidates) != 1:
            raise ValueError("National ID missing or ambiguous; confirm the client's National ID before saving")
        national_id = candidates[0]
    national_id = normalize_national_id(national_id)
    root = library_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    folder = root / national_id
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    entry_id = uuid.uuid4().hex
    destination = folder / (entry_id + ".pdf")
    metadata = folder / (entry_id + ".json")
    try:
        with source.open("rb") as src, destination.open("xb") as dst:
            os.chmod(destination, 0o600)
            shutil.copyfileobj(src, dst)
        record = {
            "id": entry_id,
            "national_id": national_id,
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
    # Include older flat-library records; never silently move them to a guessed client.
    for metadata in list(root.glob("*.json")) + list(root.glob("*/*.json")):
        try:
            record = json.loads(metadata.read_text(encoding="utf-8"))
            if record["id"] != metadata.stem or not re.fullmatch(r"[0-9a-f]{32}", record["id"]):
                continue
            pdf = metadata.with_suffix(".pdf")
            if pdf.is_file():
                records.append((record, pdf))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(records, key=lambda item: item[0]["created_at"], reverse=True)


def verify_archived_pdf(record, path):
    path = Path(path).resolve()
    root = library_root().resolve()
    national_id = record.get("national_id")
    expected_parent = root / normalize_national_id(national_id) if national_id else root
    if path.parent != expected_parent or path.name != record["id"] + ".pdf":
        raise ValueError("Document is outside its client archive")
    if sha256(path) != record["sha256"]:
        raise ValueError("Archived PDF integrity check failed")
    return path
