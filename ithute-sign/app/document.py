"""Local PDF/Word conversion and image-signature placement; source is never modified."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import fitz

ALLOWED = {'.pdf', '.docx', '.doc'}

@dataclass(frozen=True)
class Placement:
    page_index: int
    x: float
    y: float
    width: float
    height: float
    signature_png: str

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def to_pdf(path: str, destination: str) -> str:
    source = Path(path).resolve()
    if source.suffix.lower() not in ALLOWED:
        raise ValueError('Select a PDF, DOCX, or DOC file')
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() == '.pdf':
        return str(source)
    if os.name != 'nt':
        raise RuntimeError('Word conversion requires Windows with Microsoft Word installed.')
    import pythoncom
    import win32com.client
    target = Path(destination).resolve()
    if target == source:
        raise ValueError('Conversion output cannot overwrite source')
    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx('Word.Application')
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3
        doc = word.Documents.Open(str(source), ConfirmConversions=False, ReadOnly=True,
                                  AddToRecentFiles=False, OpenAndRepair=False)
        doc.ExportAsFixedFormat(str(target), 17)
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError('Word did not produce a usable PDF')
        return str(target)
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        finally:
            try:
                if word is not None:
                    word.Quit()
            finally:
                pythoncom.CoUninitialize()

def _validate(doc, placement):
    if not 0 <= placement.page_index < len(doc):
        raise ValueError('Invalid page number')
    if placement.width <= 0 or placement.height <= 0:
        raise ValueError('Signature width and height must be positive')
    page = doc[placement.page_index]
    rect = fitz.Rect(placement.x, placement.y,
                     placement.x + placement.width, placement.y + placement.height)
    if rect.is_empty or not page.rect.contains(rect):
        raise ValueError('Signature rectangle must fit entirely on page')
    image = Path(placement.signature_png)
    if not image.is_file():
        raise FileNotFoundError(image)
    if image.suffix.lower() != '.png':
        raise ValueError('Signature must be a PNG file')
    try:
        pixel = fitz.Pixmap(str(image))
    except Exception as exc:
        raise ValueError('Invalid signature PNG') from exc
    if pixel.width < 10 or pixel.height < 10:
        raise ValueError('Signature image is too small')
    return rect

def sign_pdf_many(source_pdf, placements, destination, source_document=None):
    source = Path(source_pdf).resolve()
    output = Path(destination).resolve()
    original = Path(source_document or source_pdf).resolve()
    if not placements:
        raise ValueError('At least one signature is required')
    if output in {source, original}:
        raise ValueError('Output must not overwrite source document')
    if output.suffix.lower() != '.pdf':
        raise ValueError('Output filename must end in .pdf')
    if output.exists():
        raise FileExistsError('Output already exists; choose a new filename')
    if Path(str(output) + '.audit.json').exists():
        raise FileExistsError('Audit output already exists')
    audit_path = Path(str(output) + '.audit.json')
    created_pdf = False
    created_audit = False
    try:
        with fitz.open(str(source)) as doc:
            if doc.needs_pass or len(doc) == 0:
                raise ValueError('PDF is encrypted or empty')
            rects = [_validate(doc, p) for p in placements]
            for p, rect in zip(placements, rects):
                doc[p.page_index].insert_image(rect, filename=p.signature_png,
                                               keep_proportion=True, overlay=True)
            with output.open('xb') as target:
                created_pdf = True
                target.write(doc.tobytes(garbage=4, deflate=True))
        with fitz.open(str(output)) as verify:
            if len(verify) == 0 or verify.needs_pass:
                raise RuntimeError('Exported PDF could not be verified')
        audit = {
            'format_version': 2,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'source_name': original.name,
            'source_sha256': sha256(original),
            'source_pdf_sha256': sha256(source),
            'signed_pdf_sha256': sha256(output),
            'signatures': [
                {'page_index_zero_based': p.page_index,
                 'rect_pdf_points': [p.x, p.y, p.width, p.height],
                 'signature_image_sha256': sha256(p.signature_png)}
                for p in placements
            ],
            'method': 'visual signature images; NOT a cryptographic digital signature',
        }
        with audit_path.open('x', encoding='utf-8') as f:
            created_audit = True
            json.dump(audit, f, indent=2)
        return str(audit_path)
    except BaseException:
        if created_audit:
            audit_path.unlink(missing_ok=True)
        if created_pdf:
            output.unlink(missing_ok=True)
        raise

def sign_pdf(source_pdf, signature_png, destination, page_index, x, y,
             width=160, height=65, source_document=None):
    return sign_pdf_many(source_pdf,
                         [Placement(page_index, x, y, width, height, str(signature_png))],
                         destination, source_document=source_document)
