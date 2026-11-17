"""Strict offline LoanHub Annexure C signing for the verified eight-page layout.

Only explicitly PENDING witness roles are offered. Existing signed roles are never
re-captured or overwritten. Unsupported layouts fail closed.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import fitz

@dataclass(frozen=True)
class PendingField:
    role: str
    page: int
    box: tuple
    status: fitz.Rect | None
    date: fitz.Rect | None
    method: fitz.Rect | None

def detect_loanhub(pdf):
    if len(pdf) != 8:
        raise ValueError("Unsupported LoanHub layout: expected 8 pages")
    page = pdf[6]
    text = page.get_text()
    if ("ANNEXURE C - ACCEPTANCE AND SIGNATURES" not in text
            or "BORROWER WITNESS" not in text
            or "LENDER WITNESS" not in text
            or "SINGLE SIGNATURE EXECUTION" not in pdf[5].get_text()):
        raise ValueError("Unrecognized LoanHub signature template; manual signing remains available")
    if abs(page.rect.width - 595.28) > 3 or abs(page.rect.height - 841.89) > 3:
        raise ValueError("Unsupported page dimensions")
    # Coordinates are PDF points for this exact generated LoanHub template.
    specs = [
        ("Borrower witness", (402, 276, 529, 305), fitz.Rect(494, 231, 536, 247),
         fitz.Rect(400, 312, 538, 328), fitz.Rect(399, 337, 541, 350)),
        ("Lender witness", (402, 411, 529, 441), fitz.Rect(494, 366, 536, 383),
         fitz.Rect(400, 447, 538, 463), fitz.Rect(399, 473, 541, 486)),
    ]
    found = []
    for role, box, status, date, method in specs:
        status_text = page.get_textbox(status).strip()
        date_text = page.get_textbox(date).strip()
        if status_text == "SIGNED":
            continue
        if status_text != "PENDING" or date_text != "Pending":
            raise ValueError("Unexpected status for " + role + "; review the PDF manually")
        found.append(PendingField(role, 6, box, status, date, method))
    # The two separate execution boxes must be signed even when the top
    # borrower and lender records are already marked SIGNED.
    bottom_specs = (
        ("Borrower execution", "PLACE OF BORROWER SIGNATURE", (57.6, 516.0, 239.0, 533.8),
         fitz.Rect(56, 518, 240, 535)),
        ("Lender execution", "PLACE OF LENDER SIGNATURE", (311.3, 516.0, 493.0, 533.8),
         fitz.Rect(310, 518, 494, 535)),
    )
    for role, anchor, box, underline_rect in bottom_specs:
        if len(page.search_for(anchor)) != 1:
            raise ValueError("Missing or duplicated LoanHub execution field: " + role)
        underline = page.get_textbox(underline_rect).strip()
        if underline == "________________________________":
            found.append(PendingField(role, 6, box, None, None, None))
        elif underline:
            raise ValueError("Unexpected content in " + role + "; manual review required")
        else:
            # A previously signed execution field has no placeholder line.
            # Verify it contains an image within the field; otherwise fail closed.
            region = fitz.Rect(*box)
            images = [b for b in page.get_text("dict")["blocks"]
                      if b.get("type") == 1 and fitz.Rect(b["bbox"]).intersects(region)]
            if not images:
                raise ValueError("Missing signature and placeholder for " + role)
    return found

def _replace_text(page, rect, value, fontsize=8, color=(0.09, 0.22, 0.35)):
    # Remove only text within the narrowly validated target region.
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(images=0, graphics=0, text=0)
    page.insert_textbox(rect, value, fontsize=fontsize, fontname="helv",
                        color=color, align=fitz.TEXT_ALIGN_LEFT)

def save_loanhub_signed(source, destination, captured):
    """captured: sequence of (PendingField, png_path, accepted_datetime)."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists() or destination.suffix.lower() != ".pdf":
        raise ValueError("Choose a new .pdf filename; original must remain unchanged")
    with fitz.open(source) as pdf:
        pending = detect_loanhub(pdf)
        if len(pending) != len(captured) or {x.role for x in pending} != {x.role for x, _, _ in captured}:
            raise ValueError("Every pending field must be signed exactly once")
        page = pdf[6]
        # Verify all images before modifying the document.
        for field, png, accepted in captured:
            if field not in pending or not Path(png).is_file() or accepted.tzinfo is None:
                raise ValueError("Invalid signing capture")
            image = fitz.Pixmap(str(png))
            if image.width < 10 or image.height < 10:
                raise ValueError("Invalid signature image")
        for field, png, accepted in captured:
            # White out only the existing placeholder underline, not the entire cell.
            page.add_redact_annot(fitz.Rect(*field.box), fill=(1, 1, 1))
        page.apply_redactions(images=0, graphics=0, text=0)
        for field, png, accepted in captured:
            page.insert_image(fitz.Rect(*field.box), filename=str(png), keep_proportion=True, overlay=True)
            if field.status is not None:
                _replace_text(page, field.status, "SIGNED", fontsize=7)
                _replace_text(page, field.date, accepted.strftime("%d %b %Y %H:%M %Z"), fontsize=6)
                _replace_text(page, field.method, "Wacom STU-540", fontsize=7)
            else:
                # Small timestamp stays inside the execution box, below the ink.
                stamp = fitz.Rect(field.box[0], 534.2, field.box[2], 541.8)
                page.insert_textbox(stamp, accepted.strftime("%d %b %Y %H:%M %Z"),
                                    fontsize=5.5, fontname="helv", color=(0.09, 0.22, 0.35))
        # Exclusive creation prevents accidental overwrite.
        with destination.open("xb") as out:
            out.write(pdf.tobytes(garbage=4, deflate=True))
    try:
        with fitz.open(destination) as verify:
            if len(verify) != 8 or "SIGNED" not in verify[6].get_text():
                raise ValueError("Saved PDF failed verification")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return str(destination)
