# ohmetry-seo-engine

A read-only SEO audit and reporting engine for **https://ohmetry.com/**. It crawls the site the way a polite search
bot would, records every URL's indexability, metadata, links and structured data, and produces an evidence-backed,
prioritised action plan.

It never edits the website. Every recommendation is a proposal for a human to approve.

## Status

| Phase | Scope | State |
|---|---|---|
| 1. Discovery & baseline | robots/sitemap discovery, crawler, URL inventory, baseline reports | **Built and tested.** Live baseline not yet run (see below) |
| 2. Technical SEO engine | status/redirect/canonical/indexability/metadata/heading/image/link/duplicate/structured-data audits | **Built and tested** |
| 3. Search data | GSC CSV import ✅, GSC API ✅ (untested against a live property), PageSpeed API ✅ (parser tested), GA4 ❌, dashboard ❌ | Partial |
| 4. Keyword intelligence | import, intent, clustering, keyword→URL map, cannibalisation | Not started |
| 5. Content & internal-link recommendations | briefs, quality checklist, editorial calendar | Not started |
| 6. Authority / outreach tracker | prospects, drafts only | Not started |
| 7. Monitoring | weekly GitHub Action ✅, change log / diffing ❌ | Partial |

**No Ohmetry data is in this repo yet.** The build environment couldn't reach ohmetry.com (its network policy blocked
the host), so the engine was verified against a local test site with planted defects (`tests/conftest.py`). The first
real baseline comes from running the GitHub Action or the CLI on your own machine.

## Quick start

```bash
cd ohmetry-seo-engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                       # 38 tests, ~5 s, no network needed

ohmetry-seo audit -v            # crawl ohmetry.com, write reports/generated/<date>/
ohmetry-seo audit --max-pages 50 --out reports/generated/smoke   # quick smoke run
```

At the default 1 request/second, a 300-page site takes about 6 minutes.

### With Search Console data

Export from GSC (Performance → set the date range → Export → Download CSV/ZIP), then:

```bash
ohmetry-seo audit --gsc imports/ohmetry-Performance-on-Search-2026-11-04.zip \
                  --gsc-start 2026-08-05 --gsc-end 2026-11-02
```

Always pass the date range: GSC's UI export doesn't include it, and the reports flag the range as missing if you
don't.

For the API instead (`pip install -e ".[google]"`, credentials below):

```bash
ohmetry-seo audit --gsc-api --gsc-start 2026-08-05 --gsc-end 2026-11-02
```

### With PageSpeed Insights

```bash
export PAGESPEED_API_KEY=...    # or put it in .env
ohmetry-seo audit --pagespeed
```

This tests the home page plus the top pages (by GSC impressions if imported, otherwise by shallowest click depth),
up to `pagespeed.max_urls` (default 10), on mobile and desktop.

## Credentials and setup

Everything is optional. Without credentials the engine still crawls, audits and accepts CSV exports, and the reports
mark each integration as **unconfigured**. They never show placeholder numbers.

| Integration | What you need | Where |
|---|---|---|
| PageSpeed Insights | API key restricted to the PageSpeed Insights API (free quota is ample) | Google Cloud console → APIs & Services → Credentials |
| Search Console API | Service account JSON key, with the account's email added to the property as a **Restricted** user. Enable "Google Search Console API" in the same Cloud project | Cloud console → IAM → Service accounts; GSC → Settings → Users and permissions |
| GA4 (Phase 3) | Same service account added as **Viewer** on the property; property ID in `config/site.yaml` | GA4 → Admin → Property access management |

Set `GOOGLE_APPLICATION_CREDENTIALS` to the key file path and `PAGESPEED_API_KEY` in `.env` (see `.env.example`). For
GitHub Actions, add `PAGESPEED_API_KEY` as a repository secret (Settings → Secrets and variables → Actions).
`.gitignore` excludes `.env`, key files and `imports/`. Never commit them.

Set `search_console.site_url` in `config/site.yaml` to match your property exactly: `sc-domain:ohmetry.com` for a
Domain property, or `https://ohmetry.com/` for a URL-prefix property.

## Scheduled audit (GitHub Actions)

`.github/workflows/ohmetry-seo-audit.yml` (at the repo root):

- **On push** to `ohmetry-seo-engine/**`: runs the tests only.
- **Mondays 03:17 UTC**, or **manually** (Actions → Ohmetry SEO audit → Run workflow): runs the tests, crawls
  ohmetry.com, optionally runs PageSpeed, posts the baseline summary to the run page, and uploads every report as an
  artifact kept for 90 days.

The workflow has `contents: read` permission only. It can't commit, push or deploy.

## Reports

Written to `reports/generated/<date>/`:

| File | Contents |
|---|---|
| `baseline-summary.md` | Crawl parameters, inventory counts, issue counts, GSC/PSI status with sources and date ranges, limitations |
| `priority-action-plan.md` | Issue types ranked P0→P3, each with evidence, why it matters, action, hypothesis, validation, rollback and score breakdown |
| `url-inventory.csv` | One row per URL: status, indexability + reason, canonical, robots, title/description/H1/H2, word count (diagnostic), schema types, in/out links, images, sitemap, GSC metrics if imported, issues, priority |
| `technical-audit.csv` / `.json` | Issue register: severity, class, code, URL, evidence, remediation |
| `indexability-report.csv` | robots.txt, meta robots, X-Robots-Tag, canonical, sitemap and the resulting verdict per URL |
| `metadata-report.csv` | Titles, descriptions, H1s, lang, viewport, hreflang |
| `internal-link-report.csv` | Inbound linking pages, outbound counts, click depth, top anchors |
| `broken-internal-links.csv` | Source → target → status → anchor (only written if any exist) |
| `structured-data-report.csv` | JSON-LD types, JSON errors, missing required/recommended properties, restricted types |
| `performance-baseline.csv` | PSI field (CrUX p75) and lab metrics per URL/strategy, with test timestamp; header only if not configured |

Crawl snapshots (`data/snapshots/crawl-*.json`) keep the full per-page record for later diffing. They're gitignored.

## How the crawler behaves

- Seeds: `start_url`, every URL in the sitemaps (from robots.txt `Sitemap:` lines, plus `/sitemap.xml`; indexes and
  gzip are supported).
- Honours robots.txt for its own user agent **and** for Googlebot. A URL blocked for either isn't fetched, and
  it's reported if the sitemap lists it.
- One request at a time, `delay_seconds` apart (default 1.0), retry with backoff on 429/5xx, `Retry-After`
  honoured. Identifies itself as `OhmetrySEOEngine/0.1`.
- GET only. No forms, no logins, no JavaScript execution, no off-site fetching.
- Skips crawl traps: >2 query params, repeated path segments, configured exclude patterns, non-page file types.
  Tracking params (`utm_*`, `gclid`…) are stripped during normalisation.
- Records each redirect hop, detects loops and chains, and checks that `http://` and www/apex variants 301 to
  the preferred origin.

The crawler reads **raw HTML**. If calculator content is rendered client-side, it flags `JS_DEPENDENT_CONTENT`;
confirm what Google sees with URL Inspection in GSC.

## Audit checks

The full list with rationale, action, validation and rollback is in `src/ohmetry_seo/audit/catalog.py`. Summary:

- **P0**: robots.txt unreachable, redirect loops, 5xx, host/protocol variants not consolidated
- **P1**: 4xx, soft 404, broken internal links, sitemap/robots/noindex contradictions, multiple or broken
  canonicals, missing title or viewport, JS-dependent content, orphan pages, invalid JSON-LD, exact duplicates
- **P2**: redirect chains, sitemap hygiene, duplicate titles, missing H1, near duplicates, weak internal linking,
  incomplete or restricted schema
- **P3**: length checks, meta descriptions, alt text, lang, canonical missing, heading skips, generic anchors, low
  text (diagnostic only)

Thresholds are in `config/crawler.yaml` → `audit:`. Score weights are in `config/scoring.yaml`; the score is a
triage aid, not a model of Google's ranking.

## Ground rules (from the brief)

- Read-only by default. Production changes go through recommendation → patch/branch → before/after → tests →
  human approval → normal release process → monitoring → rollback plan.
- Never invent volumes, rankings, traffic, backlinks or competitor data. Unknown stays empty.
- Never change formulas, constants, units or rounding for SEO reasons.
- No fake schema, doorway pages, hidden text, bought links or automated outreach.
- No guarantee of top-10 rankings. GSC average position is an impression-weighted average, not a fixed rank.

## Layout

```
config/              site.yaml, crawler.yaml, scoring.yaml
src/ohmetry_seo/
  urls.py            normalisation, internal/external, trap filters
  fetcher.py         rate-limited GET with per-hop redirect recording
  robots.py          robots.txt evaluation (Google's 4xx/5xx semantics)
  sitemap.py         sitemap + index + gzip, XXE-safe
  parser.py          HTML → title/meta/canonical/headings/links/images/JSON-LD/text shingles
  crawler.py         BFS crawl, PageRecord, indexability verdicts, host-variant checks
  audit/             catalog (issue knowledge), checks, links graph, duplicates, structured data
  gsc.py             GSC CSV/ZIP import, API client, prioritisation bands
  pagespeed.py       PSI API client + CrUX/Lighthouse parsing, CWV thresholds
  scoring.py         issue → recommendation grouping and transparent score
  reports.py         CSV/JSON/Markdown writers, crawl snapshots
  cli.py             `ohmetry-seo audit`
tests/               unit tests + end-to-end crawl of a local fixture site
```
