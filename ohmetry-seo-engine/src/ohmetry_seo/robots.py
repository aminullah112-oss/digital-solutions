"""robots.txt fetching and evaluation.

Follows Google's documented handling: a 4xx robots.txt means "no
restrictions"; a 5xx or network failure means "assume everything is
disallowed" (Google treats prolonged 5xx as full disallow). We're stricter
than Google on failure on purpose: if we can't read the rules we don't crawl.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .fetcher import Fetcher


@dataclass
class RobotsInfo:
    url: str
    status: int | None
    mode: str  # "rules", "allow_all", "disallow_all"
    sitemaps: list[str] = field(default_factory=list)
    raw: str = ""
    error: str | None = None
    _parser: RobotFileParser | None = None

    def can_fetch(self, user_agent: str, url: str) -> bool:
        if self.mode == "allow_all":
            return True
        if self.mode == "disallow_all":
            return False
        assert self._parser is not None
        return self._parser.can_fetch(user_agent, url)

    def googlebot_allowed(self, url: str) -> bool:
        return self.can_fetch("Googlebot", url)


def robots_url_for(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, "/robots.txt", "", ""))


def parse_robots(url: str, status: int | None, text: str, error: str | None = None) -> RobotsInfo:
    if error or status is None:
        return RobotsInfo(url, status, "disallow_all", error=error or "no response")
    if 400 <= status < 500:
        return RobotsInfo(url, status, "allow_all", raw=text)
    if status >= 500:
        return RobotsInfo(url, status, "disallow_all", raw=text, error=f"HTTP {status}")
    parser = RobotFileParser()
    parser.set_url(url)
    parser.parse(text.splitlines())
    sitemaps = [line.split(":", 1)[1].strip() for line in text.splitlines()
                if line.lower().startswith("sitemap:") and ":" in line]
    return RobotsInfo(url, status, "rules", sitemaps=sitemaps, raw=text, _parser=parser)


def fetch_robots(fetcher: Fetcher, site_url: str) -> RobotsInfo:
    url = robots_url_for(site_url)
    res = fetcher.get(url)
    text = (res.body or b"").decode("utf-8", errors="replace")
    return parse_robots(url, res.status, text, res.error)
