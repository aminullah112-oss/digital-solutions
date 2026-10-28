"""Browser control panel for a server-side tradebot.

Run `python -m tradebot web` on the bot's server behind an HTTPS reverse proxy
(deploy/Caddyfile). Standard library only, no JavaScript.

What the browser CAN do: Kite daily login, see status/positions/pending
orders/trades/logs, run backtests and comparisons, start/stop/restart the bot
service, trigger or clear the kill switch, reset a halt.

What it deliberately CANNOT do: switch paper <-> live, change risk settings or
configs, or place orders. Those stay server-side (/etc/tradebot), so a stolen
panel login can at worst stop trading, not start it. Code execution on the
server is a different matter (it can read the day's Kite token), which is why
the panel requires a password AND a TOTP code, listens only on localhost, and
keeps its own surface small.

Security measures: scrypt password hash, TOTP (RFC 6238), server-side sessions
(HttpOnly, Secure, SameSite=Lax cookies), per-form CSRF tokens plus Origin
check, login throttling, password re-entry for actions that resume trading
(reset, start/restart, clearing the kill switch), strict CSP, no-store caching
and a same-origin referrer policy (the Kite callback URL carries a request_token).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

from .config import Config

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
JOB_RE = re.compile(r"^[0-9]{8}T[0-9]{6}-[0-9a-f]{6}$")
SESSION_SECONDS = 12 * 3600
MAX_BODY = 64 * 1024


def h(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


# --------------------------------------------------------------------- crypto
def hash_password(password: str, n: int = 2 ** 14, r: int = 8, p: int = 1) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    # ':'-separated (not '$') so env files and shells never try to expand it.
    return f"scrypt:{n}:{r}:{p}:{base64.b64encode(salt).decode()}:{base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split(":")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r),
                             p=int(p), dklen=len(base64.b64decode(dk)))
        return hmac.compare_digest(got, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = int((time.time() if at is None else at) // step)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return f"{code:0{digits}d}"


def verify_totp(secret: str, code: str, at: float | None = None, window: int = 1) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit():
        return False
    now = time.time() if at is None else at
    return any(hmac.compare_digest(totp(secret, now + k * 30), code) for k in range(-window, window + 1))


# --------------------------------------------------------------------- markdown
def _inline(text: str) -> str:
    t = h(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", t)


def md_to_html(md: str) -> str:
    """Just enough Markdown for the bot's reports: headings, tables, lists,
    paragraphs, **bold**, `code`. Everything is escaped first."""
    out, table, items = [], [], []

    def flush():
        if table:
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table]
            cells = [r for r in cells if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]  # drop |---| rows
            head, body = cells[0], cells[1:]
            out.append('<div class="scroll"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>" + "".join(
                           "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</tbody></table></div>")
            table.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("|"):
            if items:
                flush()
            table.append(s)
            continue
        if s.startswith("- "):
            if table:
                flush()
            items.append(s[2:])
            continue
        flush()
        if not s.strip():
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            lvl = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
        else:
            out.append(f"<p>{_inline(s)}</p>")
    flush()
    return "\n".join(out)


# --------------------------------------------------------------------- panel
FLASH = {
    "login": "Signed in.", "logout": "Signed out.",
    "kill_on": "Kill switch ON: every bot blocks entries and flattens at the next open moment, then exits.",
    "kill_off": "Kill switch cleared. Start the bot again if it exited.",
    "reset_queued": "Reset queued; the running bot applies it on its next cycle.",
    "reset_done": "Reset applied to the saved state.",
    "svc_ok": "Service command sent.", "svc_fail": "Service command failed; see the server log.",
    "kite_ok": "Kite session saved. Running bots pick it up on their next cycle.",
    "kite_fail": "Kite login failed; nothing was saved.", "kite_nokey": "KITE_API_KEY / KITE_API_SECRET not set on the server.",
    "bad_password": "Password incorrect; nothing changed.",
    "job_started": "Backtest started.", "job_busy": "Another backtest is still running.",
    "job_bad": "Invalid backtest request.",
}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#5f6670;--line:#dfe3e8;--ok:#0f7b45;--warn:#a15c00;--bad:#b42318;--acc:#1f5eff}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--ink:#e8eaee;--mute:#9aa3ae;--line:#2a2f39;--ok:#3ccf87;--warn:#f0a640;--bad:#ff6b5e;--acc:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--card);border-bottom:1px solid var(--line)}
header nav a{margin-right:14px;color:var(--ink);text-decoration:none;font-weight:600}header nav a.on{color:var(--acc)}
main{max-width:1100px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 14px}
.card h2,.card h3{margin:0 0 8px}.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.spread{justify-content:space-between}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:8px 0}
.kv{border:1px solid var(--line);border-radius:8px;padding:8px 10px}.kv b{display:block;font-size:12px;color:var(--mute);font-weight:500}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;font-weight:700;border:1px solid currentColor}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.mute{color:var(--mute)}
.flash{border-left:4px solid var(--acc)}.alert{border-left:4px solid var(--bad)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--mute);font-weight:600}
form.inline{display:inline-flex;gap:6px;align-items:center;margin:0}
input,select,button{font:inherit;padding:7px 10px;border-radius:7px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
button{cursor:pointer;font-weight:600}button.primary{background:var(--acc);border-color:var(--acc);color:#fff}
button.danger{background:var(--bad);border-color:var(--bad);color:#fff}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;max-height:420px;font-size:12.5px}
a{color:var(--acc)}label{display:block;margin:8px 0 4px;color:var(--mute);font-size:13px}
.login{max-width:360px;margin:60px auto}
"""


class Panel:
    def __init__(self, configs_dir: str | Path, work_dir: str | Path, password_hash: str,
                 totp_secret: str | None, secure_cookies: bool = True, python: str = sys.executable,
                 run=None, env: dict | None = None):
        self.configs_dir, self.work_dir = Path(configs_dir), Path(work_dir)
        self.password_hash, self.totp_secret = password_hash, totp_secret
        self.secure = secure_cookies
        self.python = python
        self.env = dict(os.environ if env is None else env)
        self.run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=20))
        self.sessions: dict[str, dict] = {}
        self.failures: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()
        self.job_lock = threading.Lock()
        self.reports = self.work_dir / "reports"
        self.datasets = self.work_dir / "data"
        for j in self.jobs():                      # jobs orphaned by a panel restart
            if j.get("status") == "running":
                j["status"] = "interrupted"
                (self.reports / j["id"] / "job.json").write_text(json.dumps(j))

    # ---------------------------------------------------------------- configs
    def configs(self) -> dict[str, tuple[Path, Config]]:
        out = {}
        for f in sorted(self.configs_dir.glob("*.json")):
            if NAME_RE.match(f.stem):
                try:
                    out[f.stem] = (f, Config.load(f))
                except (ValueError, OSError) as e:
                    out[f.stem] = (f, e)
        return out

    def path(self, p: str | Path) -> Path:
        p = Path(p)
        return p if p.is_absolute() else self.work_dir / p

    # --------------------------------------------------------------- sessions
    def new_session(self) -> str:
        sid = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[sid] = {"exp": time.time() + SESSION_SECONDS, "csrf": secrets.token_urlsafe(24)}
        return sid

    def session(self, sid: str | None) -> dict | None:
        if not sid:
            return None
        with self.lock:
            s = self.sessions.get(sid)
            if s and s["exp"] > time.time():
                return s
            self.sessions.pop(sid, None)
        return None

    def throttled(self, ip: str) -> bool:
        q = self.failures[ip]
        while q and q[0] < time.time() - 900:
            q.popleft()
        return len(q) >= 5

    def check_credentials(self, ip: str, password: str, code: str) -> bool:
        ok = verify_password(password, self.password_hash)
        if self.totp_secret:
            ok = verify_totp(self.totp_secret, code) and ok
        if not ok:
            self.failures[ip].append(time.time())
        return ok

    # ----------------------------------------------------------------- status
    def status(self, name: str, cfg: Config) -> dict:
        sp = self.path(cfg.state_file)
        d = {"name": name, "cfg": cfg, "exists": sp.exists(), "service": self.service_state(name)}
        if sp.exists():
            try:
                d["state"] = json.loads(sp.read_text())
            except ValueError:
                d["state"] = {}
                d["error"] = "state file unreadable"
        tp = sp.with_name("trades.csv")
        d["trades"] = tp.read_text().strip().splitlines()[-8:] if tp.exists() else []
        d["kill"] = self.path(cfg.kill_switch_file).exists()
        return d

    def service_state(self, name: str) -> str:
        try:
            r = self.run(["systemctl", "is-active", f"tradebot@{name}.service"])
            return (r.stdout or "").strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            return "unknown"

    def kite_status(self) -> dict:
        from .kite import TokenStore
        store = TokenStore(self.env.get("KITE_TOKEN_FILE") or self.work_dir / "state/kite_token.json")
        try:
            d = store.load()
        except (OSError, ValueError):
            d = None
        if not d:
            return {"ok": False, "text": "not logged in today"}
        exp = pd.Timestamp(d["expires"])
        ok = pd.Timestamp.now(tz=exp.tz) < exp
        return {"ok": ok, "text": f"{'valid' if ok else 'EXPIRED'} until {exp:%d %b %H:%M} IST", "user": d.get("user_id", "")}

    def log_tail(self, cfg: Config, n: int = 150) -> str:
        lp = self.path(cfg.state_file).with_name("bot.log")
        if not lp.exists():
            return "(no log yet)"
        with open(lp, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200_000))
            return "\n".join(f.read().decode(errors="replace").splitlines()[-n:])

    # ---------------------------------------------------------------- actions
    def set_kill(self, on: bool) -> None:
        for _, (_, cfg) in self.configs().items():
            if isinstance(cfg, Exception):
                continue
            k = self.path(cfg.kill_switch_file)
            if on:
                k.parent.mkdir(parents=True, exist_ok=True)
                k.write_text(f"set from web panel {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
            else:
                k.unlink(missing_ok=True)

    def reset(self, name: str) -> str:
        from .live import engine_running, request_control
        _, cfg = self.configs()[name]
        sp = self.path(cfg.state_file)
        if not sp.exists():
            return "reset_done"
        if engine_running(sp):
            request_control(sp, reset={"by": "web panel", "at": str(pd.Timestamp.now(tz="UTC"))})
            return "reset_queued"
        from .__main__ import _offline_reset
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            _offline_reset(cfg, sp, "web panel")
        return "reset_done"

    def service(self, name: str, action: str) -> bool:
        if action not in ("start", "stop", "restart") or name not in self.configs():
            return False
        try:
            r = self.run(["systemctl", action, f"tradebot@{name}.service"])
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def kite_exchange(self, request_token: str) -> bool:
        from .kite import TokenStore, exchange_request_token
        key, secret = self.env.get("KITE_API_KEY"), self.env.get("KITE_API_SECRET")
        if not key or not secret:
            return False
        data = exchange_request_token(key, secret, request_token)
        store = TokenStore(self.env.get("KITE_TOKEN_FILE") or self.work_dir / "state/kite_token.json")
        store.save(data["access_token"], data.get("user_id", ""), pd.Timestamp.now(tz="Asia/Kolkata"))
        return True

    # ------------------------------------------------------------------- jobs
    def list_datasets(self) -> list[str]:
        if not self.datasets.is_dir():
            return []
        return sorted((d.name for d in self.datasets.iterdir() if d.is_dir() and NAME_RE.match(d.name.lower())),
                      reverse=True)

    def jobs(self) -> list[dict]:
        if not self.reports.is_dir():
            return []
        out = []
        for d in sorted(self.reports.iterdir(), reverse=True):
            if JOB_RE.match(d.name) and (d / "job.json").exists():
                try:
                    out.append(json.loads((d / "job.json").read_text()))
                except ValueError:
                    pass
        return out[:30]

    def start_job(self, names: list[str], data: str, split: float, folds: int) -> str | None:
        confs = self.configs()
        if not names or any(n not in confs or isinstance(confs[n][1], Exception) for n in names):
            raise ValueError("unknown config")
        if not (0 <= split < 1) or not (0 <= folds <= 10):
            raise ValueError("bad split/folds")
        if not self.job_lock.acquire(blocking=False):
            return None
        jid = time.strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3)
        out = self.reports / jid
        out.mkdir(parents=True)
        cmd = [self.python, "-m", "tradebot", "compare"]
        for n in names:
            cmd += ["-c", str(confs[n][0])]
        if data == "synthetic":
            cmd += ["--synthetic"]
        elif data == "download":
            ds = self.datasets / jid.lower()
            cmd += ["--download", "--save-data", str(ds)]
        elif data.startswith("dataset:") and data[8:] in self.list_datasets():
            cmd += ["--data", str(self.datasets / data[8:])]
        else:
            self.job_lock.release()
            out.rmdir()
            raise ValueError("bad data source")
        cmd += ["--split", str(split), "--folds", str(folds), "--out", str(out)]
        meta = {"id": jid, "configs": names, "data": data, "split": split, "folds": folds,
                "started": time.strftime("%Y-%m-%d %H:%M:%S"), "status": "running"}
        (out / "job.json").write_text(json.dumps(meta))

        # The job runs in the bots' working dir, so point it at this package explicitly
        # rather than relying on the caller's PYTHONPATH.
        pkg_root = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(x for x in (pkg_root, env.get("PYTHONPATH")) if x)

        def work():
            try:
                with open(out / "output.log", "w") as log:
                    rc = subprocess.run(cmd, cwd=self.work_dir, stdout=log, stderr=subprocess.STDOUT,
                                        env=env, timeout=3600).returncode
                meta.update(status="done" if rc == 0 else "failed", returncode=rc)
            except Exception as e:                      # noqa: BLE001 - recorded for the operator
                meta.update(status="failed", error=str(e))
            finally:
                meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
                (out / "job.json").write_text(json.dumps(meta))
                self.job_lock.release()
        threading.Thread(target=work, daemon=True, name=f"job-{jid}").start()
        return jid


# --------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    panel: Panel
    server_version = "tradebot"
    sys_version = ""

    # ----------------------------------------------------------- plumbing
    def log_message(self, fmt, *args):
        # Never log query strings: the Kite callback carries a request_token.
        sys.stderr.write(f"{self.client_ip()} {self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}\n")

    def client_ip(self) -> str:
        ip = self.client_address[0]
        fwd = self.headers.get("X-Forwarded-For")
        if fwd and ip in ("127.0.0.1", "::1"):
            ip = fwd.split(",")[-1].strip()        # set by the local reverse proxy
        return ip

    def cookie(self, name: str) -> str | None:
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return None

    def send(self, code: int, body: str = "", ctype: str = "text/html; charset=utf-8", headers=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        # same-origin, not no-referrer: no-referrer makes browsers send `Origin: null`
        # on form posts, which the CSRF origin check must refuse. same-origin still
        # never sends a referrer off-site, so the Kite request_token can't leak.
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'")
        if self.panel.secure:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def redirect(self, to: str, headers=None):
        self.send(303, "", headers={"Location": to, **(headers or {})})

    def set_cookie(self, sid: str, max_age: int) -> str:
        return (f"tb_session={sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}"
                + ("; Secure" if self.panel.secure else ""))

    def form(self) -> dict[str, str]:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("body too large")
        raw = self.rfile.read(n).decode(errors="replace")
        return {k: v[-1] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}

    def same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True                 # older clients; the CSRF token still applies
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        return urllib.parse.urlparse(origin).netloc == host

    # ----------------------------------------------------------- routing
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
        p = url.path
        if p == "/healthz":
            return self.send(200, "ok", "text/plain")
        if p == "/panel.css":
            return self.send(200, CSS, "text/css; charset=utf-8")
        if p == "/login":
            return self.send(200, self.page_login(q.get("msg")))
        s = self.panel.session(self.cookie("tb_session"))
        if not s:
            return self.redirect("/login")
        if p == "/":
            return self.send(200, self.page_dashboard(s, q.get("msg")))
        m = re.fullmatch(r"/instance/([a-z0-9_-]+)", p)
        if m and m.group(1) in self.panel.configs():
            return self.send(200, self.page_instance(s, m.group(1), q.get("msg")))
        if p == "/backtest":
            return self.send(200, self.page_backtest(s, q.get("msg")))
        m = re.fullmatch(r"/jobs/([0-9T-]+-[0-9a-f]{6})", p)
        if m and JOB_RE.match(m.group(1)) and (self.panel.reports / m.group(1) / "job.json").exists():
            return self.send(200, self.page_job(s, m.group(1)))
        if p == "/kite/login":
            key = self.panel.env.get("KITE_API_KEY")
            if not key:
                return self.redirect("/?msg=kite_nokey")
            from .kite import login_url
            return self.redirect(login_url(key))
        if p == "/kite/callback":
            if q.get("status") != "success" or not q.get("request_token"):
                return self.redirect("/?msg=kite_fail")
            try:
                ok = self.panel.kite_exchange(q["request_token"])
            except Exception as e:                          # noqa: BLE001 - shown generically
                sys.stderr.write(f"kite exchange failed: {type(e).__name__}\n")
                ok = False
            return self.redirect("/?msg=" + ("kite_ok" if ok else "kite_fail"))
        return self.send(404, self.layout(s, "Not found", "<div class='card'>Not found.</div>"))

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            f = self.form()
        except ValueError:
            return self.send(413, "too large", "text/plain")
        if not self.same_origin():
            return self.send(403, "cross-origin request refused", "text/plain")
        if p == "/login":
            ip = self.client_ip()
            if self.panel.throttled(ip):
                return self.send(429, self.page_login(None, "Too many failed attempts. Wait 15 minutes."))
            if self.panel.check_credentials(ip, f.get("password", ""), f.get("code", "")):
                sid = self.panel.new_session()
                return self.redirect("/?msg=login", {"Set-Cookie": self.set_cookie(sid, SESSION_SECONDS)})
            time.sleep(0.5)
            return self.send(401, self.page_login(None, "Sign-in failed."))
        sid = self.cookie("tb_session")
        s = self.panel.session(sid)
        if not s:
            return self.send(401, "not signed in", "text/plain")
        if not hmac.compare_digest(f.get("csrf", ""), s["csrf"]):
            return self.send(403, "bad CSRF token", "text/plain")
        if p == "/logout":
            with self.panel.lock:
                self.panel.sessions.pop(sid, None)
            return self.redirect("/login?msg=logout", {"Set-Cookie": self.set_cookie("", 0)})

        def confirmed() -> bool:
            # Actions that resume trading need the password again (and the TOTP code).
            ip = self.client_ip()
            return not self.panel.throttled(ip) and self.panel.check_credentials(
                ip, f.get("password", ""), f.get("code", ""))

        if p == "/killswitch":
            if f.get("state") == "on":
                self.panel.set_kill(True)
                return self.redirect("/?msg=kill_on")
            if not confirmed():
                return self.redirect("/?msg=bad_password")
            self.panel.set_kill(False)
            return self.redirect("/?msg=kill_off")
        m = re.fullmatch(r"/instance/([a-z0-9_-]+)/(reset|service)", p)
        if m and m.group(1) in self.panel.configs():
            name, what = m.groups()
            back = f"/instance/{name}"
            if what == "reset":
                if not confirmed():
                    return self.redirect(back + "?msg=bad_password")
                return self.redirect(back + "?msg=" + self.panel.reset(name))
            action = f.get("action", "")
            if action in ("start", "restart") and not confirmed():
                return self.redirect(back + "?msg=bad_password")
            ok = self.panel.service(name, action)
            return self.redirect(back + "?msg=" + ("svc_ok" if ok else "svc_fail"))
        if p == "/backtest":
            names = [k[4:] for k, v in f.items() if k.startswith("cfg_") and v == "on"]
            try:
                jid = self.panel.start_job(names, f.get("data", ""), float(f.get("split", "0.7")),
                                           int(f.get("folds", "4")))
            except ValueError:
                return self.redirect("/backtest?msg=job_bad")
            if jid is None:
                return self.redirect("/backtest?msg=job_busy")
            return self.redirect(f"/jobs/{jid}")
        return self.send(404, "not found", "text/plain")

    # ----------------------------------------------------------- pages
    def layout(self, s: dict | None, title: str, body: str, msg: str | None = None, refresh: int = 0) -> str:
        flash = f"<div class='card flash'>{h(FLASH[msg])}</div>" if msg in FLASH else ""
        nav = ""
        if s:
            here = urllib.parse.urlparse(self.path).path
            links = [("/", "Dashboard"), ("/backtest", "Backtests")]
            nav = ("<nav>" + "".join(f"<a href='{u}' class='{'on' if here == u else ''}'>{t}</a>" for u, t in links)
                   + "</nav><form class='inline' method='post' action='/logout'>"
                   + f"<input type='hidden' name='csrf' value='{h(s['csrf'])}'><button>Sign out</button></form>")
        meta = f"<meta http-equiv='refresh' content='{refresh}'>" if refresh else ""
        return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width,initial-scale=1'>{meta}"
                f"<title>{h(title)} · tradebot</title><link rel='stylesheet' href='/panel.css'></head><body>"
                f"<header><strong>tradebot</strong>{nav}</header><main>{flash}{body}</main></body></html>")

    def csrf(self, s) -> str:
        return f"<input type='hidden' name='csrf' value='{h(s['csrf'])}'>"

    def confirm_fields(self) -> str:
        code = ("<input name='code' inputmode='numeric' autocomplete='one-time-code' placeholder='TOTP code' size='8' required>"
                if self.panel.totp_secret else "")
        return f"<input type='password' name='password' placeholder='password' autocomplete='current-password' required>{code}"

    def page_login(self, msg, error: str | None = None) -> str:
        err = f"<p class='bad'>{h(error)}</p>" if error else ""
        code = ("<label>Authenticator code</label><input name='code' inputmode='numeric' "
                "autocomplete='one-time-code' required>") if self.panel.totp_secret else ""
        body = (f"<div class='card login'><h2>Sign in</h2>{err}<form method='post' action='/login'>"
                "<label>Password</label><input type='password' name='password' autocomplete='current-password' required autofocus>"
                f"{code}<p><button class='primary'>Sign in</button></p></form></div>")
        return self.layout(None, "Sign in", body, msg)

    def page_dashboard(self, s, msg) -> str:
        P = self.panel
        kite = P.kite_status()
        mode = P.env.get("TRADEBOT_MODE", "?")
        kill_any = False
        cards = []
        for name, (path, cfg) in P.configs().items():
            if isinstance(cfg, Exception):
                cards.append(f"<div class='card alert'><h3>{h(name)}</h3>Config error: {h(cfg)}</div>")
                continue
            st = P.status(name, cfg)
            kill_any |= st["kill"]
            state = st.get("state", {})
            risk = state.get("risk", {})
            halt = risk.get("hard_halted") or risk.get("entry_block") or risk.get("day_halted") or ""
            pos = state.get("positions", [])
            pend = state.get("pending", {})
            svc = st["service"]
            svc_cls = "ok" if svc == "active" else ("bad" if svc == "failed" else "mute")
            warn = [w for w, on in (
                (f"HALT: {halt}", halt),
                (f"{sum(1 for r in pend.values() if r.get('escalated'))} stop(s) need checking in Kite",
                 any(r.get("escalated") for r in pend.values())),
                ("position without confirmed stop", any(not d.get("broker_stop_id") or d.get("stop_uncertain") for d in pos)),
            ) if on]
            cards.append(
                f"<div class='card {'alert' if warn else ''}'><div class='row spread'>"
                f"<h3><a href='/instance/{h(name)}'>{h(name)}</a> <span class='mute'>{h(cfg.mode)}/{h(cfg.strategy)}</span></h3>"
                f"<span class='badge {svc_cls}'>service {h(svc)}</span></div>"
                + "".join(f"<p class='bad'><strong>{h(w)}</strong></p>" for w in warn)
                + "<div class='grid'>"
                + f"<div class='kv'><b>positions</b>{len(pos)}</div>"
                + f"<div class='kv'><b>unresolved orders</b>{len(pend)}</div>"
                + f"<div class='kv'><b>realised P&amp;L</b>{state.get('realized', 0):+,.0f}</div>"
                + f"<div class='kv'><b>state saved</b>{h(str(state.get('saved_at', 'never'))[:19])}</div>"
                + "</div></div>")
        kill_form = (
            f"<form class='inline' method='post' action='/killswitch'>{self.csrf(s)}"
            + ("<input type='hidden' name='state' value='off'>" + self.confirm_fields()
               + "<button>Clear kill switch</button>" if kill_any else
               "<input type='hidden' name='state' value='on'><button class='danger'>KILL SWITCH: flatten all &amp; stop</button>")
            + "</form>")
        top = (f"<div class='card'><div class='row spread'>"
               f"<div><h2>Overview</h2>Mode: <span class='badge {'bad' if mode == 'live' else 'ok'}'>{h(mode)}</span> "
               f"&nbsp; Kite: <span class='badge {'ok' if kite['ok'] else 'warn'}'>{h(kite['text'])}</span> "
               f"&nbsp; <a href='/kite/login'>Log in to Kite</a></div>{kill_form}</div>"
               + ("<p class='bad'><strong>Kill switch is ON.</strong></p>" if kill_any else "")
               + "<p class='mute'>Mode and risk settings are changed on the server only "
                 "(<code>/etc/tradebot</code>), never from this page.</p></div>")
        return self.layout(s, "Dashboard", top + "".join(cards), msg, refresh=60)

    def page_instance(self, s, name, msg) -> str:
        P = self.panel
        _, cfg = P.configs()[name]
        st = P.status(name, cfg)
        state = st.get("state", {})
        risk = state.get("risk", {})
        rows = []
        for d in state.get("positions", []):
            flags = " ".join(f for f, on in (("STOP UNCONFIRMED", d.get("stop_tag")), ("EXIT PENDING", d.get("exit_tag")),
                                            ("STOP UNKNOWN", d.get("stop_uncertain")),
                                            ("NO STOP", not d.get("broker_stop_id") and not d.get("stop_tag"))) if on)
            rows.append(f"<tr><td>{'LONG' if d.get('side', 1) > 0 else 'SHORT'}</td><td>{h(d.get('symbol'))}</td>"
                        f"<td>{h(d.get('qty'))}</td><td>{float(d.get('entry', 0)):,.2f}</td><td>{float(d.get('stop', 0)):,.2f}</td>"
                        f"<td>{h(d.get('target') or '-')}</td><td>{h(d.get('bars_held', 0))}</td>"
                        f"<td>{h(d.get('broker_stop_id') or '-')}</td><td class='bad'>{h(flags)}</td></tr>")
        pos = ("<div class='scroll'><table><thead><tr><th>side</th><th>symbol</th><th>qty</th><th>entry</th><th>stop</th>"
               "<th>target</th><th>bars</th><th>stop id</th><th>flags</th></tr></thead><tbody>"
               + "".join(rows) + "</tbody></table></div>") if rows else "<p class='mute'>No open positions.</p>"
        pend = state.get("pending", {})
        prow = "".join(
            f"<tr><td>{h(r.get('kind'))}</td><td>{h(r.get('symbol'))}</td><td>{h(r.get('qty'))}</td><td>{h(r.get('tag'))}</td>"
            f"<td>{h(str(r.get('created', ''))[:19])}</td><td class='{'bad' if r.get('escalated') else ''}'>"
            f"{'ESCALATED: check Kite' if r.get('escalated') else ('presumed absent' if r.get('absent') else 'resolving')}</td></tr>"
            for r in pend.values())
        pend_html = ("<div class='scroll'><table><thead><tr><th>kind</th><th>symbol</th><th>qty</th><th>tag</th><th>since</th>"
                     "<th>state</th></tr></thead><tbody>" + prow + "</tbody></table></div>") if prow else "<p class='mute'>None.</p>"
        trades = "<pre>" + h("\n".join(st["trades"]) or "(no trades yet)") + "</pre>"
        halts = [f"{k}: {v}" for k, v in risk.items() if k in ("hard_halted", "entry_block", "day_halted") and v]
        act = f"/instance/{h(name)}/service"
        svc = (f"<div class='row'><form class='inline' method='post' action='{act}'>{self.csrf(s)}"
               "<input type='hidden' name='action' value='stop'><button>Stop bot</button></form>"
               f"<form class='inline' method='post' action='{act}'>{self.csrf(s)}"
               "<select name='action'><option value='start'>start</option><option value='restart'>restart</option></select>"
               f"{self.confirm_fields()}<button>Apply</button></form></div>"
               "<p class='mute'>Stopping is safe: broker-side stops stay active. Start/restart need your password.</p>")
        reset = (f"<form class='inline' method='post' action='/instance/{h(name)}/reset'>{self.csrf(s)}"
                 f"{self.confirm_fields()}<button>Reset halt</button></form>"
                 "<p class='mute'>Only after checking the Kite order book: reset clears halts and marks escalated "
                 "stops as absent so the bot places fresh ones.</p>")
        body = (f"<div class='card'><h2>{h(name)} <span class='mute'>{h(cfg.mode)}/{h(cfg.strategy)}</span></h2>"
                f"<div class='grid'><div class='kv'><b>service</b>{h(st['service'])}</div>"
                f"<div class='kv'><b>realised P&amp;L</b>{state.get('realized', 0):+,.2f}</div>"
                f"<div class='kv'><b>loss streak</b>{h(risk.get('loss_streak', 0))}</div>"
                f"<div class='kv'><b>peak equity</b>{float(risk.get('peak_equity', cfg.initial_capital)):,.0f}</div>"
                f"<div class='kv'><b>state saved</b>{h(str(state.get('saved_at', 'never'))[:19])}</div></div>"
                + ("".join(f"<p class='bad'><strong>{h(x)}</strong></p>" for x in halts) or "<p class='ok'>No halts.</p>")
                + "</div>"
                f"<div class='card'><h3>Positions</h3>{pos}</div>"
                f"<div class='card'><h3>Unresolved orders</h3>{pend_html}</div>"
                f"<div class='card'><h3>Recent trades</h3>{trades}</div>"
                f"<div class='card'><h3>Service</h3>{svc}</div>"
                f"<div class='card'><h3>Reset</h3>{reset}</div>"
                f"<div class='card'><h3>Log (last lines)</h3><pre>{h(P.log_tail(cfg))}</pre></div>")
        return self.layout(s, name, body, msg, refresh=30)

    def page_backtest(self, s, msg) -> str:
        P = self.panel
        confs = {n: c for n, (_, c) in P.configs().items() if not isinstance(c, Exception)}
        boxes = "".join(f"<label><input type='checkbox' name='cfg_{h(n)}' value='on' {'checked' if n.startswith('swing') else ''}>"
                        f" {h(n)} <span class='mute'>({h(c.mode)}/{h(c.strategy)}, {len(c.symbols)} symbols)</span></label>"
                        for n, c in confs.items())
        opts = ("<option value='download'>Download fresh data (yfinance) and save it</option>"
                + "".join(f"<option value='dataset:{h(d)}'>Saved dataset {h(d)}</option>" for d in P.list_datasets())
                + "<option value='synthetic'>Synthetic (plumbing check only)</option>")
        form = (f"<div class='card'><h2>Run a comparison</h2><form method='post' action='/backtest'>{self.csrf(s)}"
                f"{boxes}<label>Data</label><select name='data'>{opts}</select>"
                "<div class='row'><div><label>In-sample fraction</label><input name='split' value='0.7' size='5'></div>"
                "<div><label>Periods</label><input name='folds' value='4' size='4'></div></div>"
                "<p class='mute'>Configs compared together must share mode, interval and symbols. "
                "Pick between them on reasoning or in-sample results, not on the out-of-sample column.</p>"
                "<p><button class='primary'>Run</button></p></form></div>")
        rows = "".join(f"<tr><td><a href='/jobs/{h(j['id'])}'>{h(j['id'])}</a></td><td>{h(', '.join(j.get('configs', [])))}</td>"
                       f"<td>{h(j.get('data'))}</td><td class='{'ok' if j.get('status') == 'done' else ('bad' if j.get('status') == 'failed' else 'warn')}'>"
                       f"{h(j.get('status'))}</td></tr>" for j in P.jobs())
        jobs = (f"<div class='card'><h3>Recent runs</h3><div class='scroll'><table><thead><tr><th>run</th><th>configs</th>"
                f"<th>data</th><th>status</th></tr></thead><tbody>{rows}</tbody></table></div></div>") if rows else ""
        return self.layout(s, "Backtests", form + jobs, msg)

    def page_job(self, s, jid) -> str:
        d = self.panel.reports / jid
        meta = json.loads((d / "job.json").read_text())
        running = meta.get("status") == "running"
        parts = [f"<div class='card'><h2>Run {h(jid)}</h2><p>Status: <strong>{h(meta.get('status'))}</strong>"
                 f" · configs {h(', '.join(meta.get('configs', [])))} · data {h(meta.get('data'))}</p></div>"]
        cmp = d / "compare.md"
        if cmp.exists():
            parts.append(f"<div class='card report'>{md_to_html(cmp.read_text())}</div>")
            for n in meta.get("configs", []):
                rp = d / f"report_{n}.md"
                if NAME_RE.match(n) and rp.exists():
                    parts.append(f"<details class='card'><summary><strong>Full report: {h(n)}</strong></summary>"
                                 f"{md_to_html(rp.read_text())}</details>")
        log = d / "output.log"
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-80:]) if log.exists() else ""
        parts.append(f"<details class='card' {'open' if running or meta.get('status') == 'failed' else ''}>"
                     f"<summary><strong>Output</strong></summary><pre>{h(tail)}</pre></details>")
        return self.layout(s, f"Run {jid}", "".join(parts), refresh=5 if running else 0)


def make_server(panel: Panel, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("PanelHandler", (Handler,), {"panel": panel})
    srv = ThreadingHTTPServer((host, port), handler)
    srv.daemon_threads = True
    return srv
