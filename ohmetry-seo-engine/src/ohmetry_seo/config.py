"""Load and merge the YAML config files in config/."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILES = ("site.yaml", "crawler.yaml", "scoring.yaml")


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(config_dir: str | Path, overrides: dict | None = None) -> dict[str, Any]:
    config_dir = Path(config_dir)
    merged: dict[str, Any] = {}
    for name in CONFIG_FILES:
        path = config_dir / name
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                merged = _deep_merge(merged, yaml.safe_load(fh) or {})
    if overrides:
        merged = _deep_merge(merged, overrides)
    _validate(merged)
    return merged


def _validate(cfg: dict) -> None:
    site = cfg.get("site") or {}
    if not site.get("start_url"):
        raise ValueError("config: site.start_url is required")
    if not site.get("allowed_hosts"):
        raise ValueError("config: site.allowed_hosts must list at least one host")
    crawler = cfg.setdefault("crawler", {})
    if float(crawler.get("delay_seconds", 1.0)) < 0:
        raise ValueError("config: crawler.delay_seconds cannot be negative")
    cfg.setdefault("audit", {})
