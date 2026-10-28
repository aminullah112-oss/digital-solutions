"""Web panel: authentication, CSRF, escaping, headers, actions, Kite callback,
backtest jobs. Runs the real HTTP server on a loopback port."""
import http.cookiejar
import json
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from tradebot import web
from tradebot.web import Panel, hash_password, make_server, md_to_html, totp, verify_password, verify_totp

HERE = Path(__file__).resolve().parents[1]
PASSWORD = "correct horse battery"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


class PanelCase(unittest.TestCase):
    totp_secret = web.new_totp_secret()
    secure = False

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.etc, self.work = self.tmp / "etc", self.tmp / "work"
        self.etc.mkdir()
        self.work.mkdir()
        for name in ("swing", "swing_40d"):
            shutil.copy(HERE / "config" / f"{name}.json", self.etc / f"{name}.json")
        self.calls = []

        def run(cmd):
            self.calls.append(cmd)

            class R:
                returncode = 0
                stdout = "inactive\n"
            return R()
        self.panel = Panel(self.etc, self.work, hash_password(PASSWORD), self.totp_secret,
                           secure_cookies=self.secure, run=run,
                           env={"TRADEBOT_MODE": "paper", "KITE_API_KEY": "key", "KITE_API_SECRET": "sec"})
        self.srv = make_server(self.panel, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    # ------------------------------------------------------------ helpers
    def req(self, path, data=None, headers=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        r = urllib.request.Request(self.base + path, data=body, headers=headers or {})
        try:
            resp = self.op.open(r, timeout=10)
        except urllib.error.HTTPError as e:
            resp = e
        return resp.status, dict(resp.headers), resp.read().decode()

    def login(self, password=PASSWORD, code=None):
        code = totp(self.totp_secret) if code is None else code
        return self.req("/login", {"password": password, "code": code})

    def csrf(self):
        _, _, page = self.req("/")
        return re.search(r"name='csrf' value='([^']+)'", page).group(1)

    def confirm(self):
        return {"password": PASSWORD, "code": totp(self.totp_secret)}


class TestCrypto(unittest.TestCase):
    def test_password_hash(self):
        hsh = hash_password("s3cret-password")
        self.assertTrue(verify_password("s3cret-password", hsh))
        self.assertFalse(verify_password("wrong", hsh))
        self.assertFalse(verify_password("s3cret-password", "garbage"))
        self.assertNotEqual(hsh, hash_password("s3cret-password"))      # salted

    def test_totp_rfc6238_vector(self):
        import base64
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(totp(secret, at=59, digits=8), "94287082")       # RFC 6238 appendix B
        self.assertEqual(totp(secret, at=1111111109, digits=8), "07081804")
        self.assertTrue(verify_totp(secret, totp(secret, at=1000), at=1000 + 30))  # one step of drift
        self.assertFalse(verify_totp(secret, totp(secret, at=1000), at=1000 + 120))
        self.assertFalse(verify_totp(secret, "abc"))

    def test_markdown_escapes(self):
        out = md_to_html("# T <x>\n| a | <b>c</b> |\n|---|---|\n| 1 | <script>x</script> |\n- **ok** `y`")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<th>a</th>", out)
        self.assertNotIn("---", out)
        self.assertIn("<strong>ok</strong>", out)


class TestAuth(PanelCase):
    def test_everything_needs_login_except_health(self):
        self.assertEqual(self.req("/healthz")[0], 200)
        for path in ("/", "/instance/swing", "/backtest", "/kite/login", "/kite/callback?status=success&request_token=x"):
            code, hdr, _ = self.req(path)
            self.assertEqual((code, hdr.get("Location")), (303, "/login"), path)
        self.assertEqual(self.req("/killswitch", {"state": "on"})[0], 401)
        self.assertFalse(any(self.work.rglob("STOP")))

    def test_password_and_totp_both_required(self):
        self.assertEqual(self.login(password="wrong")[0], 401)
        self.assertEqual(self.login(code="000000" if totp(self.totp_secret) != "000000" else "111111")[0], 401)
        code, hdr, _ = self.login()
        self.assertEqual(code, 303)
        self.assertIn("HttpOnly", hdr["Set-Cookie"])
        self.assertIn("SameSite=Lax", hdr["Set-Cookie"])
        self.assertEqual(self.req("/")[0], 200)

    def test_lockout_after_five_failures(self):
        for _ in range(5):
            self.login(password="nope")
        self.assertEqual(self.login()[0], 429)              # even the right password, for 15 min

    def test_forged_or_expired_session_rejected(self):
        self.login()
        for c in self.jar:
            c.value = "forged-" + c.value[7:]
        self.assertEqual(self.req("/")[0], 303)
        self.jar.clear()
        self.login()
        for s in self.panel.sessions.values():
            s["exp"] = time.time() - 1
        self.assertEqual(self.req("/")[0], 303)

    def test_logout_revokes_session(self):
        self.login()
        tok = self.csrf()
        cookie = next(iter(self.jar)).value
        self.req("/logout", {"csrf": tok})
        self.assertNotIn(cookie, self.panel.sessions)


class TestRequestSafety(PanelCase):
    def test_csrf_and_origin_enforced(self):
        self.login()
        self.assertEqual(self.req("/killswitch", {"state": "on"})[0], 403)                   # no token
        self.assertEqual(self.req("/killswitch", {"state": "on", "csrf": "x"})[0], 403)      # wrong token
        tok = self.csrf()
        for origin in ("https://evil.example", "null"):
            code, _, _ = self.req("/killswitch", {"state": "on", "csrf": tok}, {"Origin": origin})
            self.assertEqual(code, 403, origin)
        self.assertFalse(any(self.work.rglob("STOP")))
        code, _, _ = self.req("/killswitch", {"state": "on", "csrf": tok}, {"Origin": self.base})
        self.assertEqual(code, 303)

    def test_security_headers(self):
        _, hdr, _ = self.req("/login")
        self.assertIn("default-src 'none'", hdr["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", hdr["Content-Security-Policy"])
        self.assertEqual(hdr["Cache-Control"], "no-store")
        self.assertEqual(hdr["X-Frame-Options"], "DENY")
        self.assertEqual(hdr["Referrer-Policy"], "same-origin")

    def test_bot_data_is_escaped(self):
        sd = self.work / "state/swing"
        sd.mkdir(parents=True)
        evil = "<script>alert(1)</script>"
        (sd / "bot_state.json").write_text(json.dumps({
            "realized": 0, "saved_at": evil, "risk": {"entry_block": evil},
            "positions": [{"symbol": evil, "side": 1, "qty": 1, "entry": 1, "stop": 0.5, "target": None,
                           "broker_stop_id": evil}],
            "pending": {evil: {"kind": "stop", "symbol": evil, "qty": 1, "tag": evil, "created": evil}}}))
        (sd / "bot.log").write_text(evil)
        self.login()
        for path in ("/", "/instance/swing"):
            page = self.req(path)[2]
            self.assertNotIn("<script>", page, path)
            self.assertIn("&lt;script&gt;", page, path)

    def test_unknown_instance_and_job_paths(self):
        self.login()
        for path in ("/instance/nope", "/instance/..%2F..%2Fetc", "/jobs/../../etc/passwd", "/jobs/20990101T000000-zzzzzz"):
            self.assertEqual(self.req(path)[0], 404, path)
        tok = self.csrf()
        self.assertEqual(self.req("/instance/nope/service", {"csrf": tok, "action": "stop"})[0], 404)


class TestActions(PanelCase):
    def test_kill_switch_on_is_instant_off_needs_password(self):
        self.login()
        tok = self.csrf()
        self.req("/killswitch", {"csrf": tok, "state": "on"})
        self.assertTrue((self.work / "STOP").exists())
        self.assertIn("Kill switch is ON", self.req("/")[2])
        self.req("/killswitch", {"csrf": tok, "state": "off", "password": "wrong", "code": "1"})
        self.assertTrue((self.work / "STOP").exists())       # still on
        self.req("/killswitch", {"csrf": tok, "state": "off", **self.confirm()})
        self.assertFalse((self.work / "STOP").exists())

    def test_service_stop_free_start_needs_password(self):
        self.login()
        tok = self.csrf()
        self.req("/instance/swing/service", {"csrf": tok, "action": "stop"})
        self.assertIn(["systemctl", "stop", "tradebot@swing.service"], self.calls)
        self.req("/instance/swing/service", {"csrf": tok, "action": "start", "password": "x", "code": "1"})
        self.assertNotIn(["systemctl", "start", "tradebot@swing.service"], self.calls)
        self.req("/instance/swing/service", {"csrf": tok, "action": "start", **self.confirm()})
        self.assertIn(["systemctl", "start", "tradebot@swing.service"], self.calls)
        n = len(self.calls)
        self.req("/instance/swing/service", {"csrf": tok, "action": "enable", **self.confirm()})
        self.assertFalse(any(c[1] == "enable" for c in self.calls[n:]))     # only start/stop/restart

    def test_reset_queues_for_running_engine_else_edits_state(self):
        import fcntl
        from tradebot.live import control_path
        sd = self.work / "state/swing"
        sd.mkdir(parents=True)
        state = sd / "bot_state.json"
        state.write_text(json.dumps({"realized": 0, "risk": {"peak_equity": 500000, "entry_block": "x"},
                                     "positions": [], "pending": {}}))
        self.login()
        tok = self.csrf()
        lock = open(state.with_suffix(".lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)          # an engine is running
        _, hdr, _ = self.req("/instance/swing/reset", {"csrf": tok, **self.confirm()})
        self.assertIn("reset_queued", hdr["Location"])
        self.assertTrue(control_path(state).exists())
        self.assertEqual(json.loads(state.read_text())["risk"]["entry_block"], "x")   # untouched
        lock.close()
        control_path(state).unlink()
        _, hdr, _ = self.req("/instance/swing/reset", {"csrf": tok, **self.confirm()})
        self.assertIn("reset_done", hdr["Location"])
        self.assertEqual(json.loads(state.read_text())["risk"]["entry_block"], "")

    def test_kite_callback_saves_token_and_never_logs_it(self):
        import io
        import sys
        import tradebot.kite as k
        orig = k.exchange_request_token
        k.exchange_request_token = lambda key, sec, rt: {"access_token": f"AT-{rt}", "user_id": "AB1234"}
        err, sys.stderr = sys.stderr, io.StringIO()
        try:
            self.login()
            _, hdr, _ = self.req("/kite/login")
            self.assertTrue(hdr["Location"].startswith("https://kite.zerodha.com/connect/login?v=3&api_key=key"))
            _, hdr, _ = self.req("/kite/callback?action=login&status=success&request_token=RT42")
            logged = sys.stderr.getvalue()
        finally:
            k.exchange_request_token = orig
            sys.stderr = err
        self.assertIn("kite_ok", hdr["Location"])
        tok = json.loads((self.work / "state/kite_token.json").read_text())
        self.assertEqual(tok["access_token"], "AT-RT42")
        self.assertNotIn("RT42", logged)
        self.assertIn("valid until", self.req("/")[2])
        _, hdr, _ = self.req("/kite/callback?status=cancelled&request_token=RT43")
        self.assertIn("kite_fail", hdr["Location"])

    def test_backtest_job_runs_and_renders(self):
        self.login()
        tok = self.csrf()
        _, hdr, _ = self.req("/backtest", {"csrf": tok, "cfg_nope": "on", "data": "synthetic"})
        self.assertIn("job_bad", hdr["Location"])
        _, hdr, _ = self.req("/backtest", {"csrf": tok, "cfg_swing": "on", "cfg_swing_40d": "on",
                                           "data": "synthetic", "split": "0.7", "folds": "2"})
        job = hdr["Location"]
        self.assertRegex(job, r"^/jobs/\d{8}T\d{6}-[0-9a-f]{6}$")
        _, hdr2, _ = self.req("/backtest", {"csrf": tok, "cfg_swing": "on", "data": "synthetic"})
        self.assertIn("job_busy", hdr2["Location"])            # one at a time
        for _ in range(120):
            page = self.req(job)[2]
            if "Status: <strong>running" not in page:
                break
            time.sleep(1)
        self.assertIn("Status: <strong>done", page)
        self.assertIn("<th>swing_40d</th>", page)
        self.assertIn("NOT APPROVED", page)


class TestSecureCookies(PanelCase):
    secure = True

    def test_secure_flag_and_hsts(self):
        code, hdr, _ = self.login()
        self.assertIn("; Secure", hdr["Set-Cookie"])
        self.assertIn("max-age", self.req("/login")[1]["Strict-Transport-Security"])


class TestWebCommand(unittest.TestCase):
    def test_refuses_unsafe_startup(self):
        import os
        from tradebot.__main__ import main
        env = os.environ.copy()
        try:
            os.environ.pop("TRADEBOT_PANEL_PASSWORD_HASH", None)
            with self.assertRaises(SystemExit) as e:
                main(["web", "--bind", "127.0.0.1:0"])
            self.assertIn("PASSWORD_HASH", str(e.exception))
            os.environ["TRADEBOT_PANEL_PASSWORD_HASH"] = hash_password("x" * 12)
            os.environ.pop("TRADEBOT_PANEL_TOTP_SECRET", None)
            with self.assertRaises(SystemExit) as e:
                main(["web", "--bind", "127.0.0.1:0"])
            self.assertIn("TOTP", str(e.exception))
            with self.assertRaises(SystemExit) as e:
                main(["web", "--bind", "0.0.0.0:8080", "--dev"])
            self.assertIn("refusing", str(e.exception))
        finally:
            os.environ.clear()
            os.environ.update(env)


if __name__ == "__main__":
    unittest.main()
