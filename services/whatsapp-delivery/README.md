# IthuteSign WhatsApp Business delivery

This is a standalone service. **Do not deploy as production-ready yet.**
LoanHub's repository and database are not modified.

## Implemented
- Desktop signed-PDF picker (most recently saved document), phone number and
  contract reference confirmation, recipient consent check
- LoanHub bearer token revalidated server-side using existing /api/v1/auth/me
- Active company membership check
- Meta Cloud API media upload and approved document-template submission
- SQLite audit log (hash, masked recipient, actor, tenant, message ID, status)
- Meta webhook HMAC signature validation and status lookup
- Provider secrets live only on the backend

## Required before enabling production sending
1. Bind each requested PDF to a **verified LoanHub contract identifier**, tenant,
   borrower and recipient using existing read-only LoanHub APIs. Never trust
   an arbitrary uploaded PDF, manually typed reference or phone number as
   evidence of authorisation. Until this exists, leave ENABLE_WHATSAPP_SEND
   unset: all send attempts will fail closed with HTTP 503.
2. Add recipient consent records and approved WhatsApp template; template
   must have a document header and one reference text parameter.
3. Provision a Meta WhatsApp Business account, registered phone number,
   access token, app secret and webhook verify token.
4. Deploy behind HTTPS with request-size limits, rate limits, firewall,
   encrypted storage/backups and strict database permissions. Protect
   tokens and never write PDF contents to application logs.
5. Implement background queue, idempotency and reconciliation for uncertain
   provider responses; avoid duplicate sends on retries.
6. Add tests with mocked LoanHub and Meta, and run a real end-to-end
   delivery test before enabling production.
7. Make service URL configurable per trusted installation and prevent
   redirects or sending bearer tokens to untrusted hosts.

## Local backend requirements

```
pip install -r services/whatsapp-delivery/requirements.txt
uvicorn services.whatsapp_delivery.app:app
```

The directory currently uses a hyphen and cannot be imported with the
above Python module path; launch from within the directory instead:

```
cd services/whatsapp-delivery
uvicorn app:app --host 127.0.0.1 --port 8090
```

Set LOANHUB_ORIGIN=https://api.loanhub.co.ls and configure META_ACCESS_TOKEN,
META_PHONE_NUMBER_ID, META_APP_SECRET, META_VERIFY_TOKEN,
WHATSAPP_TEMPLATE_NAME, and DELIVERY_DATABASE on the server.
Do not put these secrets into the desktop app or GitHub.

Desktop uses ITHUTESIGN_DELIVERY_URL=https://your-approved-delivery-host.
This endpoint is not yet deployed.
