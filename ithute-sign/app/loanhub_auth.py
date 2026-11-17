"""LoanHub desktop login transport.

The authentication route and response schema must be confirmed against the
deployed LoanHub backend before this adapter is wired into the GUI.
"""
from __future__ import annotations
import json
import ssl
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

MAX_RESPONSE = 128 * 1024

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("LoanHub authentication redirects are not permitted")

def validate_origin(origin: str) -> str:
    parsed = urlparse(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Enter the HTTPS LoanHub server origin only")
    return origin.rstrip("/")

class LoanHubLoginTransport:
    """HTTPS JSON transport; never persists credentials or session tokens."""

    def __init__(self, origin: str):
        self.origin = validate_origin(origin)
        self._opener = build_opener(HTTPSHandler(context=ssl.create_default_context()),
                                    _NoRedirect())

    def post(self, endpoint: str, payload: dict) -> dict:
        if not endpoint.startswith("/") or endpoint.startswith("//") or "?" in endpoint or "#" in endpoint:
            raise ValueError("Invalid authentication endpoint")
        body = json.dumps(payload).encode("utf-8")
        request = Request(self.origin + endpoint, data=body, method="POST",
                          headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self._opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise ValueError("LoanHub authentication was not accepted")
                if response.headers.get("Content-Length") and int(response.headers["Content-Length"]) > MAX_RESPONSE:
                    raise ValueError("LoanHub response exceeds size limit")
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ValueError("LoanHub response exceeds size limit")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("Unexpected LoanHub response")
                return data
        except HTTPError as exc:
            raise ValueError("LoanHub login failed (HTTP %d)" % exc.code) from None
        except URLError:
            raise ConnectionError("Cannot reach the LoanHub server securely") from None
