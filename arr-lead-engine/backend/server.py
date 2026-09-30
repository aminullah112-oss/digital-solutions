"""
ARR Lead Engine backend (stateless helper API).

Endpoints (all POST except /health):
  /api/discover  Google Places text search, paginated, de-duplicated
  /api/audit     lightweight website audit (SSRF-guarded)
  /api/webhook   forwards an event to AUTOMATION_WEBHOOK (n8n / Zapier / Make)

Environment:
  GOOGLE_PLACES_API_KEY   required for /api/discover
  AUTOMATION_WEBHOOK      optional
  ARR_API_TOKEN           shared secret; clients send it as X-ARR-Token.
                          REQUIRED when HOST is not loopback.
  ARR_ALLOWED_ORIGINS     comma-separated CORS allowlist. Default: localhost
                          and file:// pages (Origin "null").
  HOST (127.0.0.1), PORT (8787)
"""
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("PORT", "8787"))
HOST = os.getenv("HOST", "127.0.0.1")
GOOGLE_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
WEBHOOK = os.getenv("AUTOMATION_WEBHOOK", "")
API_TOKEN = os.getenv("ARR_API_TOKEN", "")
ALLOWED_ORIGINS = {o.strip() for o in os.getenv("ARR_ALLOWED_ORIGINS", "").split(",") if o.strip()}
MAX_BODY = 64 * 1024
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    "places." + f for f in (
        "id", "location", "displayName", "formattedAddress", "nationalPhoneNumber", "internationalPhoneNumber",
        "websiteUri", "primaryTypeDisplayName", "rating", "userRatingCount", "googleMapsUri",
        "businessStatus",
    )
) + ",nextPageToken"


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def post_json(url, payload, headers, timeout=25):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}")


# ---------------------------------------------------------------- discovery
def parse_place(p):
    return {
        "placeId": p.get("id", ""),
        "name": p.get("displayName", {}).get("text", ""),
        "industry": p.get("primaryTypeDisplayName", {}).get("text", "") or "Other",
        "area": p.get("formattedAddress", ""),
        "phone": p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber", ""),
        "website": p.get("websiteUri", ""),
        "rating": p.get("rating", 0),
        "reviews": p.get("userRatingCount", 0),
        "mapsUrl": p.get("googleMapsUri", ""),
        "businessStatus": p.get("businessStatus", ""),
        "source": "Google Places",
        "lat": (p.get("location") or {}).get("latitude"),
        "lng": (p.get("location") or {}).get("longitude"),
    }


def parse_rect(r):
    """Validate a {low:{latitude,longitude}, high:{...}} viewport; None when absent."""
    if not r:
        return None
    try:
        low, high = r["low"], r["high"]
        rect = {"low": {"latitude": float(low["latitude"]), "longitude": float(low["longitude"])},
                "high": {"latitude": float(high["latitude"]), "longitude": float(high["longitude"])}}
    except (KeyError, TypeError, ValueError):
        raise ApiError("rect must contain low/high latitude and longitude")
    for pt in rect.values():
        if not (-90 <= pt["latitude"] <= 90 and -180 <= pt["longitude"] <= 180):
            raise ApiError("rect coordinates out of range")
    return rect


def discover(body):
    if not GOOGLE_KEY:
        raise ApiError("GOOGLE_PLACES_API_KEY is not set on the server", 503)
    query = str(body.get("query") or "").strip()
    if not query:
        kind = str(body.get("type") or "business").strip()
        area = str(body.get("area") or "Melvisharam, Tamil Nadu, India").strip()
        query = f"{kind} in {area}"
    wanted = max(1, min(int(body.get("maxResults", 20)), 60))  # Places returns 20/page, 3 pages max
    restriction = parse_rect(body.get("rect"))
    if restriction:
        query = str(body.get("type") or query).strip()  # the rectangle carries the location
    seen, out, token = set(), [], None
    while len(out) < wanted:
        payload = {"textQuery": query, "pageSize": 20}
        if restriction:
            payload["locationRestriction"] = {"rectangle": restriction}
        if token:
            payload["pageToken"] = token
        data = post_json(PLACES_URL, payload, {"X-Goog-Api-Key": GOOGLE_KEY, "X-Goog-FieldMask": FIELD_MASK})
        for raw in data.get("places", []):
            place = parse_place(raw)
            if place["placeId"] in seen or place["businessStatus"] in ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"):
                continue
            seen.add(place["placeId"])
            out.append(place)
        token = data.get("nextPageToken")
        if not token:
            break
    return out[:wanted]


# -------------------------------------------------------------------- audit
def is_public_host(host):
    """True only if every address the host resolves to is publicly routable."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            return False
    return bool(infos)


class GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ApiError("Only http/https URLs are allowed")
    if not is_public_host(parts.hostname):
        raise ApiError("URL resolves to a non-public address")


OPENER = urllib.request.build_opener(GuardedRedirect)


def audit(url):
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "No website"}
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "ARR-Lead-Engine/11"})
    try:
        with OPENER.open(req, timeout=15) as resp:
            raw = resp.read(400_000).decode("utf-8", "ignore")
            final = resp.geturl()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)[:200]}
    low = raw.lower()
    title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)[^0-9]{0,20}((?:19|20)\d{2})", low)]
    return {
        "ok": True,
        "finalUrl": final,
        "https": final.startswith("https://"),
        "hasWhatsapp": "wa.me" in low or "api.whatsapp.com" in low or "whatsapp" in low,
        "hasForm": "<form" in low,
        "hasPhone": "tel:" in low,
        "hasViewport": "name=\"viewport\"" in low or "name='viewport'" in low,
        "hasMetaDescription": "name=\"description\"" in low or "name='description'" in low,
        "copyrightYear": max(years) if years else None,
        "title": re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", title.group(1))).strip()[:120] if title else "",
    }


# ------------------------------------------------------------------- server
def cors_origin(origin):
    if not origin:
        return None
    if ALLOWED_ORIGINS:
        return origin if origin in ALLOWED_ORIGINS else None
    if origin == "null" or re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
        return origin
    return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, status=200):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        allow = cors_origin(self.headers.get("Origin"))
        if allow:
            self.send_header("Access-Control-Allow-Origin", allow)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        allow = cors_origin(self.headers.get("Origin"))
        if allow:
            self.send_header("Access-Control-Allow-Origin", allow)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-ARR-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            return self._send({"status": "ok", "placesConfigured": bool(GOOGLE_KEY), "authRequired": bool(API_TOKEN)})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        try:
            if API_TOKEN and self.headers.get("X-ARR-Token") != API_TOKEN:
                raise ApiError("Invalid or missing X-ARR-Token", 401)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError("Body too large", 413)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/discover":
                return self._send({"leads": discover(body)})
            if self.path == "/api/audit":
                return self._send({"audit": audit(body.get("website", ""))})
            if self.path == "/api/webhook":
                if WEBHOOK:
                    post_json(WEBHOOK, body, {"X-ARR-Event": str(body.get("type", "event"))[:64]})
                return self._send({"received": True, "forwarded": bool(WEBHOOK)})
            self._send({"error": "not found"}, 404)
        except ApiError as exc:
            self._send({"error": str(exc)}, exc.status)
        except urllib.error.HTTPError as exc:
            self._send({"error": f"upstream HTTP {exc.code}"}, 502)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send({"error": f"bad request: {exc}"}, 400)
        except Exception as exc:  # last resort: never leak a traceback to the client
            print("unhandled:", repr(exc), file=sys.stderr)
            self._send({"error": "internal error"}, 500)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))


def main():
    if HOST not in ("127.0.0.1", "localhost", "::1") and not API_TOKEN:
        sys.exit("Refusing to listen on %s without ARR_API_TOKEN set." % HOST)
    print(f"ARR Lead Engine backend on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
