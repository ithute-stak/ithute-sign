"""Security regression tests for the standalone WhatsApp delivery backend.

Run from services/whatsapp-delivery with: pytest -q
These tests never contact LoanHub or Meta.
"""
import base64
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def service(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location("ithutesign_whatsapp_service", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DATABASE", tmp_path / "deliveries.sqlite3")
    async def verified_actor(token, company_id):
        assert token == "test-session"
        return "test-employee"
    monkeypatch.setattr(module, "verify_loanhub", verified_actor)
    return module


def payload(company_id=None, **overrides):
    body = {
        "company_id": str(company_id or uuid4()),
        "recipient": "26657763829",
        "reference": "TEST-CONTRACT-001",
        "filename": "signed.pdf",
        "pdf_base64": base64.b64encode(b"%PDF-" + b"0" * 200).decode("ascii"),
    }
    body.update(overrides)
    return body


def test_arbitrary_pdf_is_never_sent_even_if_env_flag_enabled(service, monkeypatch):
    monkeypatch.setenv("ENABLE_WHATSAPP_SEND", "true")
    monkeypatch.setenv("META_ACCESS_TOKEN", "should-never-be-used")
    with TestClient(service.app) as client:
        response = client.post("/v1/whatsapp/contracts", json=payload(),
            headers={"Authorization": "Bearer test-session"})
    assert response.status_code == 503
    assert "verification" in response.json()["detail"].lower()
    assert not service.DATABASE.exists()


def test_invalid_pdf_rejected_before_delivery(service):
    with TestClient(service.app) as client:
        response = client.post("/v1/whatsapp/contracts",
            json=payload(pdf_base64=base64.b64encode(b"not a pdf").decode()),
            headers={"Authorization": "Bearer test-session"})
    assert response.status_code == 400


def test_send_requires_authentication(service):
    with TestClient(service.app) as client:
        response = client.post("/v1/whatsapp/contracts", json=payload())
    assert response.status_code == 401


def test_status_lookup_cannot_cross_employees(service, monkeypatch):
    delivery_id = str(uuid4())
    company_id = str(uuid4())
    with service.database() as db:
        db.execute("INSERT INTO deliveries VALUES (?,?,?,?,?,?,?,?,?,?)",
            (delivery_id, company_id, "different-employee", "****3829",
             "REF", "0" * 64, None, "accepted", 1, 1))
    with TestClient(service.app) as client:
        response = client.get("/v1/whatsapp/deliveries/" + delivery_id,
            headers={"Authorization": "Bearer test-session"})
    assert response.status_code == 403


def test_webhook_rejects_invalid_signature(service, monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-secret")
    with TestClient(service.app) as client:
        response = client.post("/v1/whatsapp/webhook",
            content=b'{"entry":[]}',
            headers={"X-Hub-Signature-256": "sha256=bad"})
    assert response.status_code == 403


def test_webhook_delivery_status_never_regresses(service, monkeypatch):
    import hashlib
    import hmac
    import json
    monkeypatch.setenv("META_APP_SECRET", "test-secret")
    message_id = "wamid.test123"
    delivery_id = str(uuid4())
    with service.database() as db:
        db.execute("INSERT INTO deliveries VALUES (?,?,?,?,?,?,?,?,?,?)",
            (delivery_id, str(uuid4()), "test-employee", "****3829",
             "REF", "0" * 64, message_id, "accepted", 1, 1))

    def event(state):
        body = json.dumps({"entry": [{"changes": [{"value": {
            "statuses": [{"id": message_id, "status": state}]
        }}]}]}).encode()
        digest = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        with TestClient(service.app) as client:
            response = client.post("/v1/whatsapp/webhook", content=body,
                headers={"X-Hub-Signature-256": "sha256=" + digest})
        assert response.status_code == 200

    event("read")
    event("sent")
    event("delivered")
    event("failed")
    with service.database() as db:
        state = db.execute("SELECT state FROM deliveries WHERE id=?",
                           (delivery_id,)).fetchone()[0]
    assert state == "read"


def test_standalone_company_identity_is_tenant_bound(monkeypatch):
    import hashlib
    from standalone_identity import verify_standalone_identity
    from fastapi import HTTPException
    company = uuid4()
    key = "its_" + "x" * 48
    monkeypatch.setenv("ITHUTESIGN_COMPANY_ID", str(company))
    monkeypatch.setenv("ITHUTESIGN_API_KEY_SHA256", hashlib.sha256(key.encode()).hexdigest())
    assert verify_standalone_identity("Bearer " + key, company) == "standalone:" + str(company)
    with pytest.raises(HTTPException) as wrong_company:
        verify_standalone_identity("Bearer " + key, uuid4())
    assert wrong_company.value.status_code == 403
    with pytest.raises(HTTPException) as wrong_key:
        verify_standalone_identity("Bearer its_" + "y" * 48, company)
    assert wrong_key.value.status_code == 401


def test_offline_registration_requires_confirmations():
    from offline_registration import OfflineDocumentRegistration, validate_registration
    from fastapi import HTTPException
    payload = OfflineDocumentRegistration(
        company_id=uuid4(), document_sha256="a" * 64,
        recipient="26650123456", reference="CONTRACT-001",
        consent_confirmed=True, signer_confirmed=True,
    )
    result = validate_registration(payload)
    assert result["verified_signature"] is False
    assert result["delivery_authorised"] is False
    payload.consent_confirmed = False
    with pytest.raises(HTTPException) as error:
        validate_registration(payload)
    assert error.value.status_code == 422
