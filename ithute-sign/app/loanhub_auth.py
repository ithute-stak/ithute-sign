"""LoanHub desktop login transport.

The authentication route and response schema must be confirmed against the
deployed LoanHub backend before this adapter is wired into the GUI.
"""
from __future__ import annotations
import json
import ssl
from urllib.parse import urlparse, urlsplit, parse_qsl
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

MAX_RESPONSE = 128 * 1024
MAX_LIST_RESPONSE = 4 * 1024 * 1024

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
        if not endpoint.startswith("/") or endpoint.startswith("//") or "#" in endpoint or "\\r" in endpoint or "\\n" in endpoint:
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

    def get_authenticated(self, endpoint: str, access_token: str, headers=None):
        """Verify session against LoanHub; never trust a login response alone."""
        parsed_endpoint = urlsplit(endpoint)
        if (not endpoint.startswith("/") or endpoint.startswith("//")
                or parsed_endpoint.scheme or parsed_endpoint.netloc or parsed_endpoint.fragment
                or any(c in endpoint for c in ("\\r", "\\n", "\\x00"))):
            raise ValueError("Invalid LoanHub endpoint")
        if parsed_endpoint.query:
            pairs = parse_qsl(parsed_endpoint.query, keep_blank_values=True)
            if parsed_endpoint.path != "/api/v1/loans/" or len(pairs) != 2 or {k for k, _ in pairs} != {"skip", "limit"}:
                raise ValueError("Unsupported LoanHub query parameters")
            values = dict(pairs)
            if not all(value.isdecimal() for value in values.values()) or int(values["limit"]) not in range(1, 501):
                raise ValueError("Invalid LoanHub pagination")
        if not isinstance(access_token, str) or not access_token or any(c.isspace() for c in access_token):
            raise ValueError("Invalid LoanHub access token")
        request_headers = {"Accept": "application/json",
                           "Authorization": "Bearer " + access_token,
                           "Cache-Control": "no-store"}
        if headers:
            if not isinstance(headers, dict) or set(headers) - {"X-Company-ID", "X-Active-Role"}:
                raise ValueError("Unsupported LoanHub request headers")
            from uuid import UUID
            if "X-Company-ID" in headers:
                request_headers["X-Company-ID"] = str(UUID(str(headers["X-Company-ID"])))
            if "X-Active-Role" in headers:
                role = str(headers["X-Active-Role"])
                if not role or not role.replace("_", "").isalnum():
                    raise ValueError("Invalid LoanHub role")
                request_headers["X-Active-Role"] = role
        request = Request(self.origin + endpoint, method="GET", headers=request_headers)
        try:
            with self._opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise ValueError("LoanHub session verification failed")
                limit = MAX_LIST_RESPONSE if parsed_endpoint.path == "/api/v1/loans/" else MAX_RESPONSE
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise ValueError("LoanHub response exceeds size limit")
                data = json.loads(raw)
                if not isinstance(data, (dict, list)):
                    raise ValueError("Invalid LoanHub response")
                return data
        except HTTPError as exc:
            raise ValueError("LoanHub session verification failed (HTTP %d)" % exc.code) from None
        except URLError:
            raise ConnectionError("Cannot reach LoanHub for session verification") from None
