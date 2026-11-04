"""Extract SEO-relevant facts from raw (unrendered) HTML."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

from bs4 import BeautifulSoup

from .urls import normalise

WORD_RE = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’.-][A-Za-z0-9]+)*")
SOFT_404_RE = re.compile(r"\b(404|page not found|not found|doesn['’]?t exist|no longer available)\b", re.I)
JS_ROOT_IDS = {"root", "app", "__next", "__nuxt", "svelte"}
BOILERPLATE_TAGS = ("script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form")


@dataclass
class Link:
    url: str
    anchor: str
    nofollow: bool


@dataclass
class Image:
    src: str | None
    alt: str | None  # None = attribute missing; "" = empty (valid for decorative images)
    has_dimensions: bool


@dataclass
class JsonLdBlock:
    raw: str
    data: object | None
    error: str | None
    types: list[str] = field(default_factory=list)


@dataclass
class PageData:
    titles: list[str] = field(default_factory=list)
    meta_descriptions: list[str] = field(default_factory=list)
    meta_robots: list[str] = field(default_factory=list)  # lowercased directives from robots+googlebot
    canonicals: list[str] = field(default_factory=list)  # absolute, as declared
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    lang: str | None = None
    viewport: str | None = None
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    jsonld: list[JsonLdBlock] = field(default_factory=list)
    has_microdata: bool = False
    word_count: int = 0
    main_text_hash: str = ""
    shingles: set[int] = field(default_factory=set, repr=False)
    script_count: int = 0
    likely_js_shell: bool = False
    soft_404_signal: bool = False

    @property
    def title(self) -> str | None:
        return self.titles[0] if self.titles else None

    @property
    def meta_description(self) -> str | None:
        return self.meta_descriptions[0] if self.meta_descriptions else None

    @property
    def noindex(self) -> bool:
        return "noindex" in self.meta_robots or "none" in self.meta_robots

    @property
    def nofollow_page(self) -> bool:
        return "nofollow" in self.meta_robots or "none" in self.meta_robots

    @property
    def structured_data_types(self) -> list[str]:
        types: list[str] = []
        for block in self.jsonld:
            types.extend(block.types)
        return sorted(set(types))

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("shingles", None)
        for block in d["jsonld"]:
            block.pop("raw", None)
        return d


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _jsonld_types(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            found.append(t)
        elif isinstance(t, list):
            found.extend(x for x in t if isinstance(x, str))
        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(_jsonld_types(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_jsonld_types(item))
    return found


def shingle_set(words: list[str], size: int = 5) -> set[int]:
    if len(words) < size:
        return {hash(" ".join(words))} if words else set()
    return {int(hashlib.md5(" ".join(words[i:i + size]).encode()).hexdigest()[:12], 16)
            for i in range(len(words) - size + 1)}


def parse_page(html: bytes | str, page_url: str, strip_params: set[str] | None = None) -> PageData:
    soup = BeautifulSoup(html, "lxml")
    data = PageData()
    data.titles = [_clean(t.get_text()) for t in soup.find_all("title") if t.find_parent("svg") is None]
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").strip().lower()
        content = meta.get("content")
        if name == "description":
            data.meta_descriptions.append(_clean(content))
        elif name in ("robots", "googlebot"):
            data.meta_robots.extend(d.strip().lower() for d in (content or "").split(",") if d.strip())
        elif name == "viewport":
            data.viewport = _clean(content)

    # <base href> changes how relative URLs resolve.
    base_tag = soup.find("base", href=True)
    base_url = normalise(base_tag["href"], page_url) if base_tag else page_url
    base_url = base_url or page_url

    for link in soup.find_all("link", href=True):
        rels = [r.lower() for r in (link.get("rel") or [])]
        if "canonical" in rels:
            data.canonicals.append(normalise(link["href"], base_url, strip_params) or link["href"])
        if "alternate" in rels and link.get("hreflang"):
            data.hreflang.append((link["hreflang"], normalise(link["href"], base_url) or link["href"]))

    html_tag = soup.find("html")
    data.lang = ((html_tag.get("lang") or "").strip() or None) if html_tag else None

    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        level, text = int(tag.name[1]), _clean(tag.get_text(" "))
        data.headings.append((level, text))
        if level == 1:
            data.h1.append(text)
        elif level == 2:
            data.h2.append(text)

    for a in soup.find_all("a", href=True):
        url = normalise(a["href"], base_url, strip_params)
        if not url:
            continue
        img = a.find("img")
        anchor = _clean(a.get_text(" ")) or _clean(a.get("aria-label")) or _clean(img.get("alt") if img else None)
        rel = [r.lower() for r in (a.get("rel") or [])]
        data.links.append(Link(url, anchor, "nofollow" in rel or data.nofollow_page))

    for img in soup.find_all("img"):
        data.images.append(Image(img.get("src") or img.get("data-src"), img.get("alt"),
                                 bool(img.get("width") and img.get("height"))))

    for script in soup.find_all("script"):
        stype = (script.get("type") or "").lower()
        if stype == "application/ld+json":
            raw = script.string or script.get_text() or ""
            try:
                parsed = json.loads(raw)
                data.jsonld.append(JsonLdBlock(raw, parsed, None, sorted(set(_jsonld_types(parsed)))))
            except json.JSONDecodeError as exc:
                data.jsonld.append(JsonLdBlock(raw, None, f"invalid JSON: {exc.msg} at line {exc.lineno}"))
        else:
            data.script_count += 1
    data.has_microdata = soup.find(attrs={"itemscope": True}) is not None

    # Main-content text: strip scripts and site chrome so templates don't make
    # every page look like a near-duplicate of every other page.
    body = soup.body or soup
    for tag in body.find_all(BOILERPLATE_TAGS):
        tag.decompose()
    main = body.find("main") or body.find(attrs={"role": "main"}) or body
    words = [w.lower() for w in WORD_RE.findall(main.get_text(" "))]
    data.word_count = len(words)
    data.main_text_hash = hashlib.sha1(" ".join(words).encode()).hexdigest() if words else ""
    data.shingles = shingle_set(words)

    # Heuristic: almost no server-rendered text plus an empty SPA mount point
    # means Google must execute JS to see the content.
    mount = next((soup.find(id=i) for i in JS_ROOT_IDS if soup.find(id=i)), None)
    empty_mount = mount is not None and len(_clean(mount.get_text())) < 20
    data.likely_js_shell = data.word_count < 50 and (empty_mount or data.script_count >= 3)

    probe = " ".join(filter(None, [data.title or "", " ".join(data.h1)]))
    data.soft_404_signal = bool(SOFT_404_RE.search(probe))
    return data
