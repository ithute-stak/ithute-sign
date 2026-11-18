"""Export a verified archived PDF without changing its protected original."""
from pathlib import Path
import shutil

from signed_library import verify_archived_pdf


def export_archived_pdf(record, source, destination):
    verified = verify_archived_pdf(record, source)
    target = Path(destination).expanduser().resolve()
    if target.suffix.lower() != ".pdf":
        raise ValueError("Export destination must be a PDF")
    if target == verified.resolve():
        raise ValueError("Cannot overwrite the archived original")
    if not target.parent.is_dir():
        raise FileNotFoundError("Export folder does not exist")
    if target.exists():
        raise FileExistsError("Export destination already exists")
    # Exclusive create protects against accidental overwrites.
    created = False
    try:
        with target.open("xb") as destination_file:
            created = True
            with verified.open("rb") as source_file:
                shutil.copyfileobj(source_file, destination_file)
    except BaseException:
        # Only remove a partial file that this call actually created.
        # An exclusive-open failure must never delete someone else's file.
        if created:
            target.unlink(missing_ok=True)
        raise
    return target
