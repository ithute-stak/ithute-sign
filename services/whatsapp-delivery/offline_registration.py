"""Independent offline-document delivery registration checks.

Registration metadata is submitted by an authenticated standalone company.
These checks are intentionally conservative: they do not certify that a PDF
contains a valid signature, nor do they authorise WhatsApp delivery.
"""
import hashlib
import re
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field

class OfflineDocumentRegistration(BaseModel):
    company_id: uuid.UUID
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    recipient: str = Field(pattern=r"^[1-9][0-9]{7,14}$")
    reference: str = Field(min_length=1, max_length=100)
    consent_confirmed: bool
    signer_confirmed: bool

def validate_registration(payload: OfflineDocumentRegistration):
    """Reject missing human confirmation, but do not treat it as proof."""
    if not payload.consent_confirmed:
        raise HTTPException(422, "Recipient consent confirmation required")
    if not payload.signer_confirmed:
        raise HTTPException(422, "Signing completion confirmation required")
    if not payload.reference.strip():
        raise HTTPException(422, "Document reference required")
    return {
        "company_id": str(payload.company_id),
        "document_sha256": payload.document_sha256,
        "recipient_last4": payload.recipient[-4:],
        "reference": payload.reference.strip(),
        "verified_signature": False,
        "delivery_authorised": False,
    }
