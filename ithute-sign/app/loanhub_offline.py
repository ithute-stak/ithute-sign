"""LoanHub offline document cache primitives.

No signing permission is granted by caching. Server-issued authorization,
consent, version checks and execution must be enforced by a separate workflow.
"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

def _uuid(value: str) -> str:
    return str(UUID(str(value)))

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def validate_document(pdf: bytes, expected_sha256: str) -> None:
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("LoanHub document is not a PDF")
    if len(pdf) > 30 * 1024 * 1024:
        raise ValueError("LoanHub document exceeds offline cache limit")
    if len(expected_sha256) != 64 or _sha256(pdf) != expected_sha256.lower():
        raise ValueError("LoanHub source PDF hash mismatch")

def document_key(company_id: str, contract_id: str, version: str) -> str:
    if not version or len(version) > 128:
        raise ValueError("Document version is required")
    identity = f"{_uuid(company_id)}:{_uuid(contract_id)}:{version}"
    return hashlib.sha256(identity.encode()).hexdigest()

def cache_verified_pdf(root: Path, *, company_id: str, contract_id: str,
                       version: str, pdf: bytes, expected_sha256: str) -> Path:
    """Store only a hash-verified PDF; never mark it signed or authorized.

    Caller must provide an app-controlled private directory on an encrypted disk.
    This module intentionally does not claim encryption or offline authorization.
    """
    validate_document(pdf, expected_sha256)
    key = document_key(company_id, contract_id, version)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    target = root / (key + ".pdf")
    metadata = root / (key + ".json")
    record = {
        "company_id": _uuid(company_id),
        "contract_id": _uuid(contract_id),
        "version": version,
        "sha256": expected_sha256.lower(),
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "signing_authorized": False,
        "execution_status": "not_executed",
    }
    def atomic_write(destination: Path, data: bytes) -> None:
        fd, name = tempfile.mkstemp(prefix=".ithutesign-", dir=root)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    atomic_write(target, pdf)
    atomic_write(metadata, json.dumps(record, sort_keys=True).encode())
    return target

def open_cached_pdf(root: Path, *, company_id: str, contract_id: str,
                    version: str) -> bytes:
    key = document_key(company_id, contract_id, version)
    root = Path(root)
    metadata = json.loads((root / (key + ".json")).read_text())
    if (metadata.get("company_id") != _uuid(company_id)
            or metadata.get("contract_id") != _uuid(contract_id)
            or metadata.get("version") != version):
        raise ValueError("Cached document identity mismatch")
    pdf = (root / (key + ".pdf")).read_bytes()
    validate_document(pdf, metadata["sha256"])
    return pdf
