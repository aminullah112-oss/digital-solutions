"""A small local website with known, deliberately planted SEO defects."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ohmetry_seo.config import load_config
from ohmetry_seo.fetcher import Fetcher

LONG_TEXT = " ".join(f"word{i} explains the voltage drop formula with units and assumptions" for i in range(40))
CALC_TEXT = ("The three phase power calculator computes real power from line voltage, line current and power "
             "factor using P equals root three times V times I times PF. ") * 8


def page(title, body, *, desc="A useful description of this electrical engineering calculator page.",
         canonical=None, robots=None, lang="en", viewport=True, extra_head=""):
    head = [f"<title>{title}</title>" if title is not None else ""]
    if desc:
        head.append(f'<meta name="description" content="{desc}">')
    if canonical:
        head.append(f'<link rel="canonical" href="{canonical}">')
    if robots:
        head.append(f'<meta name="robots" content="{robots}">')
    if viewport:
        head.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    lang_attr = f' lang="{lang}"' if lang else ""
    nav = '<nav><a href="/">Home</a> <a href="/calculators/three-phase-power">3-phase</a></nav>'
    return (f"<!doctype html><html{lang_attr}><head>{''.join(head)}{extra_head}</head>"
            f"<body>{nav}<main>{body}</main><footer>© Test</footer></body></html>")


def build_site(base: str) -> dict:
    breadcrumb = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList",'
                  '"itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"' + base + '/"},'
                  '{"@type":"ListItem","position":2,"name":"Three phase"}]}</script>')
    website = ('<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
               '{"@type":"WebSite","name":"Ohmetry","url":"' + base + '/"},{"@type":"Organization","name":"Ohmetry"}]}</script>')
    routes = {
        "/robots.txt": (200, "text/plain", f"User-agent: *\nDisallow: /private/\nSitemap: {base}/sitemap.xml\n"),
        "/sitemap.xml": (200, "application/xml",
                         '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         f'<sitemap><loc>{base}/sitemap-pages.xml</loc></sitemap></sitemapindex>'),
        "/sitemap-pages.xml": (200, "application/xml",
                               '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                               + "".join(f"<url><loc>{base}{p}</loc><lastmod>2026-01-01</lastmod></url>" for p in [
                                   "/", "/calculators/three-phase-power", "/guides/voltage-drop", "/orphan-guide",
                                   "/noindexed", "/gone", "/private/secret", "/old-page", "/dup-a", "/dup-b"])
                               + "</urlset>"),
        "/": (200, "text/html", page("Ohmetry test home — electrical calculators",
                                     f"<h1>Electrical calculators</h1><p>{LONG_TEXT}</p>"
                                     '<a href="/guides/voltage-drop">Voltage drop guide</a>'
                                     '<a href="/gone">click here</a>'
                                     '<a href="/old-page">Old page</a>'
                                     '<a href="/dup-a">Dup A</a><a href="/dup-b">Dup B</a>'
                                     '<a href="/no-meta">No meta</a>'
                                     '<a href="/spa">App</a>'
                                     '<a href="/calculators/three-phase-power?utm_source=x">tracked</a>'
                                     '<a href="https://external.example/">external</a>'
                                     '<img src="/a.png" alt="diagram" width="10" height="10"><img src="/b.png">',
                                     canonical=f"{base}/", extra_head=website)),
        "/calculators/three-phase-power": (200, "text/html", page(
            "Three phase power calculator (kW, kVA, PF) | Ohmetry",
            f"<h1>Three phase power calculator</h1><h2>Formula</h2><h4>Skipped level</h4><p>{CALC_TEXT}</p>"
            '<a href="/guides/voltage-drop">Voltage drop</a>',
            canonical=f"{base}/calculators/three-phase-power", extra_head=breadcrumb)),
        "/guides/voltage-drop": (200, "text/html", page(
            "Voltage drop guide",
            f"<h1>Voltage drop</h1><h1>Second H1</h1><p>{LONG_TEXT} unique guide content</p>"
            '<script type="application/ld+json">{"@type": "TechArticle", bad json}</script>',
            canonical=f"{base}/guides/voltage-drop")),
        "/orphan-guide": (200, "text/html", page("Orphan guide about protection relays",
                                                 f"<h1>Relays</h1><p>{LONG_TEXT} relays relays coordination</p>",
                                                 canonical=f"{base}/orphan-guide")),
        "/noindexed": (200, "text/html", page("Noindexed page title here", "<h1>Hidden</h1>", robots="noindex,follow")),
        "/old-page": (301, "/old-page-2", ""),
        "/old-page-2": (301, "/calculators/three-phase-power", ""),
        "/dup-a": (200, "text/html", page("Duplicate page title", f"<h1>Dup</h1><p>{CALC_TEXT}</p>",
                                          canonical=f"{base}/dup-a")),
        "/dup-b": (200, "text/html", page("Duplicate page title", f"<h1>Dup</h1><p>{CALC_TEXT}</p>",
                                          canonical=f"{base}/dup-a")),
        "/no-meta": (200, "text/html", page(None, "<p>Short.</p>", desc=None, lang=None, viewport=False)),
        "/spa": (200, "text/html", '<!doctype html><html lang="en"><head><title>App shell page title</title>'
                                   '<meta name="viewport" content="width=device-width"></head><body><div id="root"></div>'
                                   '<script src="/a.js"></script><script src="/b.js"></script></body></html>'),
        "/private/secret": (200, "text/html", page("Secret", "<h1>Secret</h1>")),
    }
    return routes


class _Handler(BaseHTTPRequestHandler):
    routes: dict = {}
    hits: list = []

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        self.hits.append(self.path)
        route = self.routes.get(path)
        if route is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><title>Not found</title></html>")
            return
        status, ctype, body = route
        self.send_response(status)
        if status in (301, 302):
            self.send_header("Location", ctype)
            self.end_headers()
            return
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


@pytest.fixture()
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    _Handler.routes = build_site(base)
    _Handler.hits = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield base, _Handler
    server.shutdown()


@pytest.fixture()
def site_cfg(site, tmp_path):
    base, _ = site
    cfg = load_config(__import__("pathlib").Path(__file__).resolve().parents[1] / "config", {
        "site": {"start_url": base + "/", "allowed_hosts": ["127.0.0.1"]},
        "crawler": {"delay_seconds": 0, "retries": 0, "timeout_seconds": 5},
    })
    return cfg


@pytest.fixture()
def fast_fetcher():
    return Fetcher("TestBot/1.0", delay_seconds=0, timeout_seconds=5, retries=0)
