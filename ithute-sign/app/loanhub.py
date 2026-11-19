"""Strict offline LoanHub Annexure C signing for the verified eight-page layout.

Only explicitly PENDING witness roles are offered. Existing signed roles are never
re-captured or overwritten. Unsupported layouts fail closed.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import pymupdf as fitz

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
            # A printed status alone cannot establish that a witness signed.
            # Preserve signed witness fields only when an actual image is
            # present in that witness signature box.
            region = fitz.Rect(*box)
            images = [
                block for block in page.get_text("dict")["blocks"]
                if block.get("type") == 1
                and region.contains(fitz.Rect(block["bbox"]))
            ]
            if not images:
                raise ValueError(
                    "Witness marked SIGNED but no signature image was found: "
                    + role + "; manual review required")
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
                      if b.get("type") == 1 and region.contains(fitz.Rect(b["bbox"]))]
            if not images:
                raise ValueError("Missing signature and placeholder for " + role)
    return found

def inspect_loanhub_signatures(pdf):
    """Return verified pending fields and distinguish records from execution ink.

    A SIGNED record in the table is not evidence that the separate execution
    signature box contains ink. Never infer one from the other.
    """
    pending = detect_loanhub(pdf)
    roles = {field.role for field in pending}
    page = pdf[6]
    # The printed record labels are not cryptographic or handwritten proof.
    # Avoid guessing their locations from unrelated execution coordinates.
    records = {"Borrower": "not independently verified",
               "Lender": "not independently verified"}
    return {
        "pending_roles": tuple(field.role for field in pending),
        "record_status": records,
        "execution_status": {
            "Borrower": "needs fresh signature" if "Borrower execution" in roles else "image present",
            "Lender": "needs authorized signature" if "Lender execution" in roles else "image present",
        },
        "witness_status": {
            role: "pending" if role in roles else "not pending"
            for role in ("Borrower witness", "Lender witness")
        },
    }


def _replace_text(page, rect, value, fontsize=8, color=(0.09, 0.22, 0.35)):
    # Remove only text within the narrowly validated target region.
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(images=0, graphics=0, text=0)
    page.insert_textbox(rect, value, fontsize=fontsize, fontname="helv",
                        color=color, align=fitz.TEXT_ALIGN_LEFT)

def save_loanhub_signed(source, destination, captured):
    """captured: (field, png, timestamp, method) with an explicit method."""
    if any(len(entry) != 4 for entry in captured):
        raise ValueError("Every signature must specify its capture method")
    if any(entry[3] not in ("Stored employee signature", "Wacom STU-540") for entry in captured):
        raise ValueError("Unsupported signature capture method")
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists() or destination.suffix.lower() != ".pdf":
        raise ValueError("Choose a new .pdf filename; original must remain unchanged")
    with fitz.open(source) as pdf:
        pending = detect_loanhub(pdf)
        if len(pending) != len(captured) or {x.role for x in pending} != {entry[0].role for entry in captured}:
            raise ValueError("Every pending field must be signed exactly once")
        if len({entry[0].role for entry in captured}) != len(captured):
            raise ValueError("Duplicate signature role")
        page = pdf[6]
        # Verify all images before modifying the document.
        for field, png, accepted, method in captured:
            if field not in pending or not Path(png).is_file() or accepted.tzinfo is None:
                raise ValueError("Invalid signing capture")
            image = fitz.Pixmap(str(png))
            if image.width < 10 or image.height < 10:
                raise ValueError("Invalid signature image")
        for field, png, accepted, method in captured:
            # White out only the existing placeholder underline, not the entire cell.
            page.add_redact_annot(fitz.Rect(*field.box), fill=(1, 1, 1))
        page.apply_redactions(images=0, graphics=0, text=0)
        for field, png, accepted, method in captured:
            page.insert_image(fitz.Rect(*field.box), filename=str(png), keep_proportion=True, overlay=True)
            if field.status is not None:
                _replace_text(page, field.status, "SIGNED", fontsize=7)
                _replace_text(page, field.date, accepted.strftime("%d %b %Y %H:%M %Z"), fontsize=6)
                _replace_text(page, field.method, method, fontsize=6)
            else:
                # Use an explicit baseline: a 7.6pt textbox can silently
                # reject text when font ascenders/descenders exceed its height.
                # The timestamp sits below the signature image.
                timestamp = accepted.strftime("%d %b %Y %H:%M %Z")
                page.insert_text((field.box[0], 540.0), timestamp,
                                 fontsize=5.5, fontname="helv",
                                 color=(0.09, 0.22, 0.35))
        # Exclusive creation prevents accidental overwrite.
        with destination.open("xb") as out:
            out.write(pdf.tobytes(garbage=4, deflate=True))
    try:
        with fitz.open(source) as original, fitz.open(destination) as verified:
            if len(verified) != len(original) or len(verified) != 8:
                raise ValueError("Signed PDF page count changed")
            if any(verified[i].get_text() != original[i].get_text()
                   for i in range(len(original)) if i != 6):
                raise ValueError("Non-signature page text changed")
            original_page = original[6]
            signed_page = verified[6]
            # Only validate the newly captured fields. Pre-existing signed
            # records are not proof of a handwritten signature.
            for field, png, accepted, method in captured:
                rect = fitz.Rect(*field.box)
                images = [block for block in signed_page.get_text("dict")["blocks"]
                          if block.get("type") == 1
                          and fitz.Rect(block["bbox"]).intersects(rect)]
                original_images = [block for block in original_page.get_text("dict")["blocks"]
                                   if block.get("type") == 1
                                   and fitz.Rect(block["bbox"]).intersects(rect)]
                if len(images) <= len(original_images):
                    raise ValueError("Signature image missing: " + field.role)
                if field.status is not None:
                    if "SIGNED" not in signed_page.get_textbox(field.status):
                        raise ValueError("SIGNED status missing: " + field.role)
                    if "Pending" in signed_page.get_textbox(field.date):
                        raise ValueError("Pending date not replaced: " + field.role)
                    if method not in signed_page.get_textbox(field.method):
                        raise ValueError("Capture method missing: " + field.role)
                else:
                    stamp = fitz.Rect(field.box[0], 533.5, field.box[2], 544.5)
                    expected_stamp = accepted.strftime("%d %b %Y %H:%M %Z")
                    if expected_stamp not in signed_page.get_textbox(stamp):
                        raise ValueError("Execution timestamp missing: " + field.role)
            if not destination.stat().st_size:
                raise ValueError("Signed PDF is empty")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return str(destination)
