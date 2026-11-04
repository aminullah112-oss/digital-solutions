"""Command-line entry point: `ohmetry-seo audit ...`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .audit import run_audit
from .config import load_config
from .crawler import Crawler
from .gsc import fetch_search_analytics, load_gsc_exports, page_metrics
from .pagespeed import run_pagespeed
from .reports import save_snapshot, write_reports
from .scoring import build_recommendations

# Paths resolve against the working directory so the tool works the same
# whether installed editable or as a regular package (CI).
def _root() -> Path:
    return Path.cwd()


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cmd_audit(args: argparse.Namespace) -> int:
    overrides: dict = {"crawler": {}}
    if args.max_pages:
        overrides["crawler"]["max_pages"] = args.max_pages
    if args.delay is not None:
        overrides["crawler"]["delay_seconds"] = args.delay
    if args.start_url:
        overrides["site"] = {"start_url": args.start_url}
    cfg = load_config(args.config, overrides)

    gsc, gsc_status = [], "unconfigured"
    if args.gsc:
        gsc = load_gsc_exports(args.gsc, args.gsc_start, args.gsc_end)
        gsc_status = f"CSV import ({len(gsc)} file(s))" if gsc else "CSV import found no usable files"
    elif args.gsc_api:
        if not (args.gsc_start and args.gsc_end):
            print("--gsc-api needs --gsc-start and --gsc-end (YYYY-MM-DD)", file=sys.stderr)
            return 2
        site_url = cfg.get("search_console", {}).get("site_url")
        try:
            gsc = [fetch_search_analytics(site_url, args.gsc_start, args.gsc_end, ["page"]),
                   fetch_search_analytics(site_url, args.gsc_start, args.gsc_end, ["query"])]
            gsc_status = f"API ({site_url})"
        except Exception as exc:  # report, don't pretend
            gsc_status = f"API error: {exc}"
            logging.error(gsc_status)

    crawl = Crawler(cfg).run()
    audit = run_audit(crawl, cfg)
    recs = build_recommendations(audit, cfg, page_metrics(gsc))

    psi_rows, psi_status = [], "unconfigured"
    if args.pagespeed:
        targets = _pagespeed_targets(crawl, audit, page_metrics(gsc), int(cfg.get("pagespeed", {}).get("max_urls", 10)))
        try:
            psi_rows = run_pagespeed(targets)
            psi_status = f"API ({len(targets)} URL(s) × mobile/desktop)"
        except RuntimeError as exc:
            psi_status = str(exc)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else _root() / "reports" / "generated" / stamp
    written = write_reports(out, crawl, audit, recs, gsc, psi_rows, psi_status, gsc_status)
    save_snapshot(_root() / "data" / "snapshots" / f"crawl-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json", crawl)
    print(f"Crawled {sum(1 for p in crawl.pages.values() if p.fetched)} URLs, {len(audit.issues)} issues, "
          f"{len(recs)} issue types.")
    for p in written:
        print(f"  {p}")
    return 0


def _pagespeed_targets(crawl, audit, gsc_pages: dict, limit: int) -> list[str]:
    """Home page first, then highest-impression pages if GSC data exists, else shallowest pages."""
    indexable = list(audit.audited_pages)
    if gsc_pages:
        ranked = sorted((u for u in indexable if u in gsc_pages), key=lambda u: -(gsc_pages[u].get("impressions") or 0))
    else:
        ranked = sorted(indexable, key=lambda u: (crawl.pages[u].depth, u))
    ordered = [crawl.start_url] + [u for u in ranked if u != crawl.start_url]
    return ordered[:limit]


def main(argv: list[str] | None = None) -> int:
    _load_dotenv(_root() / ".env")
    ap = argparse.ArgumentParser(prog="ohmetry-seo", description="Read-only SEO audit for ohmetry.com")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="crawl the site and write the baseline report set")
    a.add_argument("--config", default=str(_root() / "config"))
    a.add_argument("--out", help="output directory (default reports/generated/<date>)")
    a.add_argument("--start-url", help="override site.start_url")
    a.add_argument("--max-pages", type=int)
    a.add_argument("--delay", type=float, help="seconds between requests (default from config)")
    a.add_argument("--gsc", help="GSC export: CSV file, folder of CSVs, or the .zip from the GSC UI")
    a.add_argument("--gsc-api", action="store_true", help="pull page+query data from the Search Console API")
    a.add_argument("--gsc-start", help="YYYY-MM-DD start of the GSC date range")
    a.add_argument("--gsc-end", help="YYYY-MM-DD end of the GSC date range")
    a.add_argument("--pagespeed", action="store_true", help="run PageSpeed Insights on priority URLs (needs PAGESPEED_API_KEY)")
    a.set_defaults(func=cmd_audit)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
