"""Standalone IthuteSign WhatsApp Business delivery service.

Deployment requirements:
- HTTPS reverse proxy and authenticated network perimeter
- LOANHUB_ORIGIN, META_ACCESS_TOKEN, META_PHONE_NUMBER_ID,
  META_APP_SECRET, META_VERIFY_TOKEN, WHATSAPP_TEMPLATE_NAME
- WhatsApp approved document template with a document header and
  a single body parameter for contract reference.
No changes to LoanHub are required.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field

app = FastAPI(title="IthuteSign WhatsApp Delivery", docs_url=None, redoc_url=None)
DATABASE = Path(os.environ.get("DELIVERY_DATABASE", "/var/lib/ithutesign-delivery/delivery.sqlite3"))
MAX_PDF = 20 * 1024 * 1024
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v22.0")


def config(key):
    value = os.environ.get(key, "").strip()
    if not value:
        raise HTTPException(503, "Delivery service not configured")
    return value


def database():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DATABASE), timeout=15)
    db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
      id TEXT PRIMARY KEY, company_id TEXT NOT NULL, actor_id TEXT NOT NULL,
      recipient_mask TEXT NOT NULL, reference TEXT NOT NULL,
      pdf_sha256 TEXT NOT NULL, meta_message_id TEXT UNIQUE,
      state TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
    )""")
    db.commit()
    return db


class ContractRequest(BaseModel):
    company_id: uuid.UUID
    recipient: str = Field(min_length=8, max_length=15, pattern=r"^[1-9][0-9]{7,14}$")
    reference: str = Field(min_length=1, max_length=100)
    filename: str = Field(min_length=5, max_length=180)
    pdf_base64: str = Field(min_length=8, max_length=28_000_000)


async def verify_loanhub(token, company_id):
    """Verify bearer token and active membership with LoanHub on every send."""
    origin = config("LOANHUB_ORIGIN")
    if urlparse(origin).scheme != "https":
        raise HTTPException(503, "LoanHub HTTPS configuration required")
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
        try:
            response = await client.get(origin.rstrip("/") + "/api/v1/auth/me",
                headers={"Authorization": "Bearer " + token})
            response.raise_for_status()
            user = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(401, "LoanHub session verification failed")
    if not isinstance(user, dict) or user.get("is_active") is not True:
        raise HTTPException(403, "Inactive LoanHub account")
    memberships = user.get("memberships", [])
    if not isinstance(memberships, list) or not any(
        isinstance(m, dict) and m.get("is_active") is True
        and str(m.get("company_id")) == str(company_id) for m in memberships
    ):
        raise HTTPException(403, "No active membership for this company")
    return str(user["id"])


@app.post("/v1/whatsapp/contracts", status_code=202)
async def send_contract(payload: ContractRequest, authorization: str = Header(default="")):
    if not authorization.startswith("Bearer ") or len(authorization) > 8192:
        raise HTTPException(401, "LoanHub bearer token required")
    actor = await verify_loanhub(authorization[7:], payload.company_id)
    try:
        data = base64.b64decode(payload.pdf_base64, validate=True)
    except (ValueError, Exception):
        raise HTTPException(400, "Invalid PDF encoding")
    if not data.startswith(b"%PDF-") or not (100 <= len(data) <= MAX_PDF):
        raise HTTPException(400, "Invalid PDF file")
    if not payload.filename.lower().endswith(".pdf") or Path(payload.filename).name != payload.filename:
        raise HTTPException(400, "Invalid PDF filename")
    # Do not trust the desktop's filename as proof of contract ownership.
    # Production deployments must additionally bind the document to an
    # authorised LoanHub contract ID before enabling sends.
    if os.environ.get("ENABLE_WHATSAPP_SEND") != "true":
        raise HTTPException(503, "Sending disabled until contract ownership validation is configured")
    delivery_id = str(uuid.uuid4())
    now = int(time.time())
    digest = hashlib.sha256(data).hexdigest()
    with closing(database()) as db:
        db.execute("INSERT INTO deliveries VALUES (?,?,?,?,?,?,?,?,?,?)",
            (delivery_id, str(payload.company_id), actor, "****" + payload.recipient[-4:],
             payload.reference, digest, None, "submitting", now, now))
        db.commit()
    api_base = "https://graph.facebook.com/" + GRAPH_VERSION
    headers = {"Authorization": "Bearer " + config("META_ACCESS_TOKEN")}
    phone_id = config("META_PHONE_NUMBER_ID")
    try:
        async with httpx.AsyncClient(timeout=35, follow_redirects=False) as client:
            media = await client.post(api_base + "/" + phone_id + "/media",
                headers=headers, data={"messaging_product": "whatsapp"},
                files={"file": (payload.filename, data, "application/pdf")})
            media.raise_for_status()
            media_id = media.json()["id"]
            message = await client.post(api_base + "/" + phone_id + "/messages",
                headers={**headers, "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": payload.recipient,
                      "type": "template", "template": {
                          "name": config("WHATSAPP_TEMPLATE_NAME"),
                          "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "en")},
                          "components": [
                              {"type": "header", "parameters": [
                                  {"type": "document", "document": {"id": media_id,
                                   "filename": payload.filename}}]},
                              {"type": "body", "parameters": [
                                  {"type": "text", "text": payload.reference}]}]}})
            message.raise_for_status()
            message_id = message.json()["messages"][0]["id"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        with closing(database()) as db:
            db.execute("UPDATE deliveries SET state='submission_failed',updated_at=? WHERE id=?",
                (int(time.time()), delivery_id))
            db.commit()
        raise HTTPException(502, "WhatsApp provider did not accept delivery")
    with closing(database()) as db:
        db.execute("UPDATE deliveries SET state='accepted',meta_message_id=?,updated_at=? WHERE id=?",
            (message_id, int(time.time()), delivery_id))
        db.commit()
    return {"delivery_id": delivery_id, "status": "accepted"}


@app.get("/v1/whatsapp/deliveries/{delivery_id}")
async def delivery_status(delivery_id: uuid.UUID, authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "LoanHub session required")
    with closing(database()) as db:
        row = db.execute("SELECT company_id,actor_id,state FROM deliveries WHERE id=?",
            (str(delivery_id),)).fetchone()
    if not row:
        raise HTTPException(404, "Delivery not found")
    actor = await verify_loanhub(authorization[7:], row[0])
    if actor != row[1]:
        raise HTTPException(403, "Delivery belongs to another employee")
    return {"delivery_id": str(delivery_id), "status": row[2]}


@app.get("/v1/whatsapp/webhook")
async def webhook_verify(request: Request):
    query = request.query_params
    if (query.get("hub.mode") == "subscribe" and
        hmac.compare_digest(query.get("hub.verify_token", ""), config("META_VERIFY_TOKEN"))):
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(query.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@app.post("/v1/whatsapp/webhook")
async def webhook_status(request: Request, x_hub_signature_256: str = Header(default="")):
    raw = await request.body()
    expected = "sha256=" + hmac.new(config("META_APP_SECRET").encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(x_hub_signature_256, expected):
        raise HTTPException(403, "Invalid webhook signature")
    try:
        payload = json.loads(raw)
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for status in change.get("value", {}).get("statuses", []):
                    state = status.get("status")
                    if state not in ("sent", "delivered", "read", "failed"):
                        continue
                    with closing(database()) as db:
                        db.execute("UPDATE deliveries SET state=?,updated_at=? WHERE meta_message_id=?",
                            (state, int(time.time()), status.get("id")))
                        db.commit()
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Invalid webhook payload")
    return {"ok": True}
