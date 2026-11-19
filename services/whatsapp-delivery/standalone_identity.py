"""Standalone IthuteSign delivery identities (independent of LoanHub).

Provision identities out-of-band using a secret manager. No credentials or
plaintext API keys are persisted by this module. The WhatsApp send route
remains disabled until signed-document and recipient checks are implemented.
"""
import hashlib
import hmac
import os
import uuid

from fastapi import HTTPException


def verify_standalone_identity(authorization: str, company_id: uuid.UUID):
    """Authenticate a provisioned company API key using constant-time digest comparison.

    ITHUTESIGN_COMPANY_ID: UUID for the provisioned company.
    ITHUTESIGN_API_KEY_SHA256: hex SHA-256 of a random >=32-byte secret.
    """
    if not authorization.startswith("Bearer ") or len(authorization) > 8192:
        raise HTTPException(401, "IthuteSign delivery credential required")
    company = os.environ.get("ITHUTESIGN_COMPANY_ID", "").strip()
    expected = os.environ.get("ITHUTESIGN_API_KEY_SHA256", "").strip().lower()
    if not company or len(expected) != 64:
        raise HTTPException(503, "Standalone delivery identity not provisioned")
    try:
        configured_company = uuid.UUID(company)
        bytes.fromhex(expected)
    except ValueError:
        raise HTTPException(503, "Invalid standalone identity configuration")
    if configured_company != company_id:
        raise HTTPException(403, "Credential is not authorised for this company")
    provided = authorization[7:]
    if not 32 <= len(provided) <= 512 or any(c.isspace() for c in provided):
        raise HTTPException(401, "Invalid IthuteSign credential")
    digest = hashlib.sha256(provided.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(digest, expected):
        raise HTTPException(401, "Invalid IthuteSign credential")
    return "standalone:" + str(company_id)
