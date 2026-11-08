"""Load and validate the YAML project configuration. All project values come from here, never from calculation modules."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from ohmetry_dc.models import ConfigError, Status, DesignException, LoadItem, Parameter, ProjectConfig, ProjectMeta

log = logging.getLogger("ohmetry_dc.config")


def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"{path} is not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return data


def _params(block: dict, prefix: str, where: str) -> dict[str, Parameter]:
    out: dict[str, Parameter] = {}
    for key, raw in block.items():
        pid = f"{prefix}.{key}"
        if not isinstance(raw, dict):
            raise ConfigError(f"{where}: '{pid}' must be a mapping of parameter fields")
        try:
            out[pid] = Parameter(id=pid, **raw)
        except (ValidationError, TypeError) as e:
            raise ConfigError(f"{where}: invalid parameter '{pid}': {e}") from None
    return out


def apply_overrides(params: dict[str, Parameter], dist: dict, path: Path) -> int:
    """Apply supplied manufacturer, utility and site data from the overrides file over the master configuration.

    The master file is never edited. The original value and source are kept on the parameter, and the overrides file keeps an append-only history.
    A manufacturer-specific parameter becomes MANUFACTURER_DATA; a project or site input stays USER_INPUT.
    """
    if not path.exists():
        return 0
    data = _read(path)
    if data.get("schema_version") != 1:
        raise ConfigError(f"{path}: unsupported schema_version {data.get('schema_version')!r} (expected 1)")
    n = 0
    for o in data.get("overrides") or []:
        pid = o.get("parameter")
        if not pid or not str(o.get("source", "")).strip():
            raise ConfigError(f"{path}: every override needs a parameter and a source document (got {o!r})")
        value = o.get("value")
        if value is None:
            continue
        if pid in params:
            old = params[pid]
            if o.get("unit") not in (None, "", old.unit):
                raise ConfigError(f"{path}: {pid} is in {old.unit}, but the override gives {o['unit']!r}")
            status = old.status.value if old.status.value == "USER_INPUT" else "MANUFACTURER_DATA"
            ref = f" ({o['datasheet_reference']})" if o.get("datasheet_reference") else ""
            params[pid] = old.model_copy(update={"value": value, "status": Status(status), "source": f"{o['source']}{ref}", "revision": "OVERRIDE", "value_ref": None,
                                                 "original_value": old.original_value if old.original_value is not None else old.value,
                                                 "original_source": old.original_source or old.source, "datasheet_revision": o.get("datasheet_revision"),
                                                 "override_date": o.get("date")})
        elif pid.startswith("distribution."):
            _, tag, field = pid.split(".", 2)
            for group in ("feeders", "busducts", "switchgear", "protection_devices"):
                hit = next((it for it in dist.get(group) or [] if it["tag"] == tag and field in it), None)
                if hit is not None:
                    hit.setdefault("original_values", {}).setdefault(field, hit[field])
                    hit[field] = value
                    hit.setdefault("data_sources", {})[field] = {"source": o["source"], "datasheet_revision": o.get("datasheet_revision")}
                    break
            else:
                raise ConfigError(f"{path}: {pid} does not exist in the distribution schedule")
        else:
            raise ConfigError(f"{path}: unknown parameter {pid!r}")
        n += 1
    return n


def load_config(project_path: str | Path, load_schedule_path: str | Path | None = None, exceptions_path: str | Path | None = None,
                distribution_path: str | Path | None = None) -> ProjectConfig:
    project_path = Path(project_path)
    data = _read(project_path)
    if data.get("schema_version") != 1:
        raise ConfigError(f"{project_path}: unsupported schema_version {data.get('schema_version')!r} (expected 1)")
    try:
        meta = ProjectMeta(**data["project"])
    except (KeyError, ValidationError, TypeError) as e:
        raise ConfigError(f"{project_path}: invalid 'project' block: {e}") from None

    params: dict[str, Parameter] = {}
    for section, block in (data.get("sections") or {}).items():
        if not isinstance(block, dict):
            raise ConfigError(f"{project_path}: section '{section}' must be a mapping")
        params.update(_params(block, section, str(project_path)))

    items: list[LoadItem] = []
    if load_schedule_path is not None:
        ls = _read(Path(load_schedule_path))
        if ls.get("schema_version") != 2:
            raise ConfigError(f"{load_schedule_path}: unsupported schema_version {ls.get('schema_version')!r} (expected 2)")
        seen: set[str] = set()
        for raw in ls.get("load_items") or []:
            try:
                item = LoadItem(**raw)
            except (ValidationError, TypeError) as e:
                raise ConfigError(f"{load_schedule_path}: invalid load item {raw.get('id', '?')!r}: {e}") from None
            if item.id in seen:
                raise ConfigError(f"{load_schedule_path}: duplicate load item id '{item.id}'")
            seen.add(item.id)
            items.append(item)

    # A value_ref points at another parameter, so the number lives in one place only.
    for pid, p in list(params.items()):
        if p.value_ref is not None:
            if p.value_ref not in params:
                raise ConfigError(f"{pid}: value_ref '{p.value_ref}' does not exist")
            if params[p.value_ref].value_ref is not None:
                raise ConfigError(f"{pid}: value_ref '{p.value_ref}' must point at a parameter that holds its own value")
            params[pid] = p.model_copy(update={"value": params[p.value_ref].value, "value_ref": None})

    resolved: list[LoadItem] = []
    for item in items:
        if item.unit_rating_ref is not None:
            if item.unit_rating_ref not in params:
                raise ConfigError(f"load item {item.id}: unit_rating_ref '{item.unit_rating_ref}' does not exist")
            v = params[item.unit_rating_ref].value
            item = item.model_copy(update={"unit_rating_kw": float(v) if isinstance(v, (int, float)) else None, "unit_rating_ref": None, "rating_from": item.unit_rating_ref})
        resolved.append(item)

    # Design exceptions and the distribution schedule sit next to the project file unless a path is given.
    base = project_path.parent
    exc_path = Path(exceptions_path) if exceptions_path else base / "design_exceptions.yaml"
    exceptions: list[DesignException] = []
    if exc_path.exists():
        for raw in _read(exc_path).get("exceptions") or []:
            try:
                exceptions.append(DesignException(**raw))
            except (ValidationError, TypeError) as e:
                raise ConfigError(f"{exc_path}: invalid exception {raw.get('id', '?')!r}: {e}") from None
    dist: dict = {}
    dpath = Path(distribution_path) if distribution_path else base / "distribution.yaml"
    if dpath.exists():
        dist = _read(dpath)
        if dist.get("schema_version") != 1:
            raise ConfigError(f"{dpath}: unsupported schema_version {dist.get('schema_version')!r} (expected 1)")

    overrides = apply_overrides(params, dist, base / "manufacturer_data_overrides.yaml")
    cfg = ProjectConfig(schema_version=1, project=meta, parameters=params, load_items=resolved, exceptions=exceptions, distribution=dist, base_dir=str(base))
    log.info("Loaded %d parameters and %d load items (%d required inputs missing now, %d deferred to later stages)", len(params), len(resolved), len(cfg.missing()), len(cfg.deferred()))
    return cfg
