"""WhatsApp delivery client. No Meta credentials are stored on the workstation."""
import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

MAX_PDF_BYTES = 20 * 1024 * 1024


def normalise_whatsapp_number(value):
    digits = re.sub(r"[\\s()+-]", "", value.strip())
    if not digits.isdecimal():
        raise ValueError("Enter a valid WhatsApp phone number")
    if len(digits) == 8:
        digits = "266" + digits
    if not (8 <= len(digits) <= 15) or digits.startswith("0"):
        raise ValueError("Use an international WhatsApp number, e.g. +266...")
    return digits


def validate_delivery_url(origin):
    parsed = urlparse(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("The delivery service must use an HTTPS origin")
    return origin.rstrip("/")


def submit_signed_contract(origin, access_token, company_id, number, pdf_path, reference):
    """Send a signed PDF to our secure delivery service, not directly to Meta."""
    origin = validate_delivery_url(origin)
    number = normalise_whatsapp_number(number)
    path = Path(pdf_path)
    if not path.is_file() or path.stat().st_size > MAX_PDF_BYTES:
        raise ValueError("Signed PDF missing or too large")
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("Only a signed PDF can be sent")
    import base64
    body = json.dumps({
        "company_id": company_id,
        "recipient": number,
        "reference": reference,
        "filename": path.name,
        "pdf_base64": base64.b64encode(data).decode("ascii"),
    }).encode("utf-8")
    request = Request(origin + "/v1/whatsapp/contracts",
        data=body, method="POST",
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=45, context=ssl.create_default_context()) as response:
            result = json.loads(response.read(65537))
            if not isinstance(result, dict) or not result.get("delivery_id"):
                raise ValueError("Unexpected delivery service response")
            return result
    except HTTPError as exc:
        raise ValueError("Delivery service rejected request (HTTP %s)" % exc.code) from None
    except URLError:
        raise ConnectionError("Cannot reach secure WhatsApp delivery service") from None
