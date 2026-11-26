"""Tests for the Nifty 100 list loader. Uses a real copy of NSE's CSV and a fake downloader."""

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nifty100  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "ind_nifty100list.csv"
CSV_TEXT = FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.setenv("NIFTY100_CACHE_FILE", str(tmp_path / "nifty100.csv"))
    nifty100._memory.update(rows=None, at=0.0, source=None)
    return tmp_path / "nifty100.csv"


def test_parse_real_csv():
    rows = nifty100.parse_csv(CSV_TEXT)
    assert len(rows) == 100
    assert rows[0] == {"symbol": "ABB", "company": "ABB India Ltd.", "industry": "Capital Goods"}
    symbols = {r["symbol"] for r in rows}
    assert {"M&M", "BAJAJ-AUTO"} <= symbols  # punctuation survives


def test_parse_handles_bom_and_duplicates():
    text = "﻿" + CSV_TEXT + "Duplicate Ltd.,X,ABB,EQ,INE000000000\n"
    rows = nifty100.parse_csv(text)
    assert len(rows) == 100


def test_parse_rejects_html_error_page():
    with pytest.raises(nifty100.ConstituentsError):
        nifty100.parse_csv("<html><body>Access Denied</body></html>")


def test_parse_rejects_truncated_file():
    short = "\n".join(CSV_TEXT.splitlines()[:10])
    with pytest.raises(nifty100.ConstituentsError):
        nifty100.parse_csv(short)


def test_falls_back_to_second_source(monkeypatch, clean):
    tried = []

    def fake_download(url):
        tried.append(url)
        if "niftyindices" in url:
            raise ConnectionError("blocked")
        return CSV_TEXT

    monkeypatch.setattr(nifty100, "_download", fake_download)
    rows, meta = nifty100.load_constituents()
    assert len(rows) == 100
    assert tried == list(nifty100.SOURCES)
    assert meta == {"source": nifty100.SOURCES[1], "stale": False}
    assert clean.exists()  # saved for next time


def test_memory_cache_avoids_second_download(monkeypatch):
    calls = []
    monkeypatch.setattr(nifty100, "_download", lambda url: calls.append(url) or CSV_TEXT)
    nifty100.load_constituents()
    nifty100.load_constituents()
    assert len(calls) == 1


def test_fresh_disk_cache_used_without_download(monkeypatch, clean):
    clean.write_text(CSV_TEXT, encoding="utf-8")

    def boom(url):
        raise AssertionError("should not download")

    monkeypatch.setattr(nifty100, "_download", boom)
    rows, meta = nifty100.load_constituents()
    assert len(rows) == 100 and meta == {"source": "cache", "stale": False}


def test_stale_cache_used_when_every_download_fails(monkeypatch, clean):
    clean.write_text(CSV_TEXT, encoding="utf-8")
    old = time.time() - 3 * 24 * 3600
    os.utime(clean, (old, old))

    def boom(url):
        raise ConnectionError("offline")

    monkeypatch.setattr(nifty100, "_download", boom)
    rows, meta = nifty100.load_constituents()
    assert len(rows) == 100 and meta == {"source": "cache", "stale": True}


def test_error_when_nothing_works(monkeypatch):
    def boom(url):
        raise ConnectionError("offline")

    monkeypatch.setattr(nifty100, "_download", boom)
    with pytest.raises(nifty100.ConstituentsError) as exc:
        nifty100.load_constituents()
    assert "niftyindices.com" in str(exc.value)
