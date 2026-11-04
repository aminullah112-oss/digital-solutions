import gzip

import pytest

from ohmetry_seo.audit.duplicates import jaccard
from ohmetry_seo.audit.structured_data import validate_jsonld
from ohmetry_seo.parser import parse_page
from ohmetry_seo.robots import parse_robots
from ohmetry_seo.sitemap import parse_sitemap_xml
from ohmetry_seo.urls import normalise, trap_reason


# --- URL normalisation ------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("HTTPS://Ohmetry.COM:443/a//b?b=2&a=1#frag", "https://ohmetry.com/a/b?a=1&b=2"),
    ("https://ohmetry.com", "https://ohmetry.com/"),
    ("https://ohmetry.com/x/?utm_source=a&id=3", "https://ohmetry.com/x/?id=3"),
    ("mailto:a@b.c", None),
    ("javascript:void(0)", None),
    ("ftp://ohmetry.com/", None),
    ("https://ohmetry.com:99999/", None),
])
def test_normalise(raw, expected):
    assert normalise(raw, strip_params={"utm_source"}) == expected


def test_normalise_relative_and_trailing_slash_preserved():
    assert normalise("../b/", "https://ohmetry.com/a/c/") == "https://ohmetry.com/a/b/"
    assert normalise("/a", "https://ohmetry.com/") != normalise("/a/", "https://ohmetry.com/")


def test_trap_reason():
    cfg = {"max_query_params": 2, "max_repeated_segments": 3, "exclude_patterns": [r"/wp-admin/"]}
    assert trap_reason("https://x.com/a?b=1&c=2&d=3", cfg)
    assert trap_reason("https://x.com/a/a/a/a/", cfg)
    assert trap_reason("https://x.com/wp-admin/x", cfg)
    assert trap_reason("https://x.com/calculators/ohms-law?unit=v", cfg) is None


# --- robots -----------------------------------------------------------------

def test_robots_rules_and_sitemaps():
    r = parse_robots("https://x.com/robots.txt", 200,
                     "User-agent: *\nDisallow: /private/\n\nUser-agent: Googlebot\nDisallow: /nogoogle/\nSitemap: https://x.com/s.xml\n")
    assert r.can_fetch("AnyBot", "https://x.com/public")
    assert not r.can_fetch("AnyBot", "https://x.com/private/a")
    assert not r.googlebot_allowed("https://x.com/nogoogle/a")
    assert r.sitemaps == ["https://x.com/s.xml"]


def test_robots_status_handling():
    assert parse_robots("u", 404, "").mode == "allow_all"
    assert parse_robots("u", 503, "").mode == "disallow_all"
    assert parse_robots("u", None, "", "timeout").mode == "disallow_all"


# --- sitemaps ---------------------------------------------------------------

URLSET = (b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          b'<url><loc> https://x.com/a </loc><lastmod>2026-01-01</lastmod></url><url><loc>https://x.com/b</loc></url></urlset>')


def test_sitemap_urlset_and_gzip():
    kind, items = parse_sitemap_xml(URLSET)
    assert kind == "urlset" and items == [("https://x.com/a", "2026-01-01"), ("https://x.com/b", None)]
    assert parse_sitemap_xml(gzip.compress(URLSET)) == (kind, items)


def test_sitemap_index_and_no_namespace():
    kind, items = parse_sitemap_xml(b"<sitemapindex><sitemap><loc>https://x.com/s1.xml</loc></sitemap></sitemapindex>")
    assert kind == "sitemapindex" and items[0][0] == "https://x.com/s1.xml"


def test_sitemap_rejects_xxe_and_non_sitemap():
    xxe = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY e SYSTEM "file:///etc/passwd">]><urlset><url><loc>&e;</loc></url></urlset>'
    _, items = parse_sitemap_xml(xxe)
    assert all("root:" not in loc for loc, _ in items)
    with pytest.raises(ValueError):
        parse_sitemap_xml(b"<html></html>")


# --- HTML parsing -----------------------------------------------------------

HTML = """<!doctype html><html lang="en-GB"><head>
<title> Ohm's law calculator </title><meta name="description" content="Calculate V, I, R.">
<meta name="robots" content="index, follow"><meta name="googlebot" content="noindex">
<link rel="canonical" href="/ohms-law"><link rel="alternate" hreflang="de" href="/de/ohms-law">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage"},{"@type":["TechArticle"],"headline":"x"}]}</script>
<script type="application/ld+json">{oops}</script>
</head><body><nav><a href="/">Home</a></nav><main>
<h1>Ohm's law</h1><h2>Formula</h2><h3>Units</h3>
<p>Voltage equals current times resistance.</p>
<a href="/watts" rel="nofollow">Watts</a><a href="#top">Top</a><a href="mailto:x@y.z">Mail</a>
<a href="/img-link"><img src="i.png" alt="Icon"></a>
<img src="a.png"><img src="b.png" alt="" width="1" height="1">
</main><footer>Footer text</footer></body></html>"""


def test_parse_page_extracts_metadata():
    d = parse_page(HTML, "https://ohmetry.com/ohms-law")
    assert d.title == "Ohm's law calculator"
    assert d.meta_description == "Calculate V, I, R."
    assert d.noindex  # googlebot meta wins
    assert d.canonicals == ["https://ohmetry.com/ohms-law"]
    assert d.hreflang == [("de", "https://ohmetry.com/de/ohms-law")]
    assert d.lang == "en-GB"
    assert d.h1 == ["Ohm's law"] and d.h2 == ["Formula"]
    assert [lvl for lvl, _ in d.headings] == [1, 2, 3]
    assert d.structured_data_types == ["TechArticle", "WebPage"]
    assert sum(1 for b in d.jsonld if b.error) == 1


def test_parse_page_links_and_images():
    d = parse_page(HTML, "https://ohmetry.com/ohms-law")
    urls = {l.url: l for l in d.links}
    assert "https://ohmetry.com/watts" in urls and urls["https://ohmetry.com/watts"].nofollow is True
    assert urls["https://ohmetry.com/img-link"].anchor == "Icon"
    assert not any(u.startswith("mailto") for u in urls)
    alts = [i.alt for i in d.images]
    assert alts == ["Icon", None, ""]  # missing vs empty are distinguished


def test_main_text_excludes_nav_and_footer():
    d = parse_page(HTML, "https://ohmetry.com/ohms-law")
    assert d.word_count < 20
    assert "footer" not in " ".join(str(d.word_count))


def test_js_shell_detection():
    shell = '<html><head><title>App</title></head><body><div id="root"></div><script src="a.js"></script></body></html>'
    assert parse_page(shell, "https://x.com/").likely_js_shell
    assert not parse_page(HTML, "https://x.com/").likely_js_shell


def test_soft_404_signal():
    assert parse_page("<html><title>Page not found</title><h1>Oops</h1></html>", "https://x.com/").soft_404_signal
    assert not parse_page("<html><title>Ohm's law</title></html>", "https://x.com/").soft_404_signal


# --- structured data --------------------------------------------------------

def test_structured_data_rules():
    f = validate_jsonld({"@type": "Organization", "name": "Ohmetry"})
    assert {"type": "Organization", "kind": "missing_required", "detail": "url"} in f
    f = validate_jsonld({"@type": "FAQPage", "mainEntity": [1]})
    assert any(x["kind"] == "restricted" for x in f)
    f = validate_jsonld({"@type": "BreadcrumbList", "itemListElement": [{"position": 1, "name": "Home"}, {"position": 2, "name": "B"}]})
    assert any("item 1: item" in x["detail"] for x in f)
    assert not any("item 2" in x["detail"] for x in f)  # last item may omit URL


def test_jaccard():
    assert jaccard({1, 2, 3}, {1, 2, 3}) == 1.0
    assert jaccard(set(), {1}) == 0.0
    assert jaccard({1, 2}, {2, 3}) == pytest.approx(1 / 3)
