import json, os, sys, threading, unittest, urllib.request, urllib.error
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import server


def call(port, path, body=None, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers=headers or {}, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read()), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), e.headers


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def test_health(self):
        self.assertEqual(call(self.port, "/health")[1]["status"], "ok")

    def test_ssrf_blocked(self):
        for url in ("http://127.0.0.1/", "http://169.254.169.254/latest/meta-data", "http://localhost:8787", "http://10.0.0.1", "file:///etc/passwd"):
            code, body, _ = call(self.port, "/api/audit", {"website": url})
            self.assertEqual(code, 400, url)

    def test_token_required_when_set(self):
        with mock.patch.object(server, "API_TOKEN", "s3cret"):
            self.assertEqual(call(self.port, "/api/audit", {"website": "x.com"})[0], 401)
            self.assertEqual(call(self.port, "/api/webhook", {"type": "t"}, {"X-ARR-Token": "s3cret"})[0], 200)

    def test_cors(self):
        _, _, h = call(self.port, "/health", headers={"Origin": "http://localhost:5500"})
        self.assertEqual(h["Access-Control-Allow-Origin"], "http://localhost:5500")
        _, _, h = call(self.port, "/health", headers={"Origin": "https://evil.example"})
        self.assertIsNone(h["Access-Control-Allow-Origin"])

    def test_discover_paginates_and_dedupes(self):
        pages = [
            {"places": [{"id": "a", "displayName": {"text": "A"}}, {"id": "b", "displayName": {"text": "B"}, "businessStatus": "CLOSED_PERMANENTLY"}], "nextPageToken": "t"},
            {"places": [{"id": "a", "displayName": {"text": "A"}}, {"id": "c", "displayName": {"text": "C"}}]},
        ]
        with mock.patch.object(server, "GOOGLE_KEY", "k"), mock.patch.object(server, "post_json", side_effect=pages):
            out = server.discover({"type": "shop", "area": "x", "maxResults": 60})
        self.assertEqual([p["placeId"] for p in out], ["a", "c"])

    def test_discover_rect_restricts_location(self):
        seen = []
        def fake(url, payload, headers, timeout=25):
            seen.append(payload)
            return {"places": [{"id": "r1", "displayName": {"text": "R"}, "location": {"latitude": 12.9, "longitude": 79.2}}]}
        rect = {"low": {"latitude": 12.8, "longitude": 79.1}, "high": {"latitude": 13.0, "longitude": 79.3}}
        with mock.patch.object(server, "GOOGLE_KEY", "k"), mock.patch.object(server, "post_json", side_effect=fake):
            out = server.discover({"type": "clinic", "area": "Ambur", "maxResults": 20, "rect": rect})
        self.assertEqual(seen[0]["textQuery"], "clinic")
        self.assertEqual(seen[0]["locationRestriction"], {"rectangle": rect})
        self.assertEqual((out[0]["lat"], out[0]["lng"]), (12.9, 79.2))
        with self.assertRaises(server.ApiError):
            server.parse_rect({"low": {"latitude": 99, "longitude": 0}, "high": {"latitude": 1, "longitude": 1}})

    def test_discover_requires_key(self):
        with mock.patch.object(server, "GOOGLE_KEY", ""):
            self.assertEqual(call(self.port, "/api/discover", {"type": "x"})[0], 503)

    def test_bad_json(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/audit", data=b"{nope", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
