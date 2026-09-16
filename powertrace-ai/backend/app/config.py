"""Application configuration.

Everything that differs between a bench setup and a plant installation lives
here and is driven by environment variables.  Nothing in this file encodes a
controller-specific assumption.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POWERTRACE_", env_file=".env", extra="ignore")

    # --- Core -------------------------------------------------------------
    app_name: str = "PowerTrace AI"
    environment: str = "development"

    # PostgreSQL in production.  SQLite is supported so the application can be
    # run on a laptop in a plant with no database server, which is a real
    # field constraint, not a development shortcut.
    database_url: str = "sqlite:///./powertrace.db"

    # --- Auth -------------------------------------------------------------
    # Must be overridden in production; startup refuses to run with the
    # default value when environment != development.
    secret_key: str = "dev-only-insecure-key-change-me"
    access_token_ttl_minutes: int = 12 * 60

    # --- Safety interlocks ------------------------------------------------
    # Hard kill-switch for any future control path.  The protocol adapters
    # ship with no write implementation at all; this flag exists so that an
    # operator can see, in Settings, that control is disabled by policy and
    # not merely unimplemented.
    allow_control_writes: bool = False

    # Nominal voltage above which a measurement channel must declare an
    # external isolating device (PT/VT/CT/transducer).  60 V is the usual
    # low-voltage boundary used for touch-safe limits.
    direct_input_voltage_limit_v: float = 60.0

    # --- Polling ----------------------------------------------------------
    default_poll_interval_ms: int = 1000
    min_poll_interval_ms: int = 100
    modbus_timeout_s: float = 3.0
    modbus_retries: int = 2
    # A value older than this is reported as STALE rather than shown as live.
    stale_after_s: float = 5.0
    # In-memory trend buffer depth per signal (about 1 h at 1 s polling).
    history_depth: int = 3600

    # --- Demo mode --------------------------------------------------------
    # Demo mode is opt-in and is surfaced permanently in the UI.  Simulated
    # values are tagged SIMULATED at the source and never lose that tag.
    demo_mode: bool = True

    # --- AI layer ---------------------------------------------------------
    # The AI layer is optional.  With no provider configured the diagnostic
    # engine still produces deterministic results; the AI section simply
    # reports that it is unavailable.
    ai_provider: str = "none"  # none | anthropic
    ai_model: str = "claude-sonnet-5"
    ai_api_key: str | None = None

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


class InsecureConfiguration(RuntimeError):
    """Raised when a production start would leave a known door open."""


def check_production_config(settings: "Settings", environ: dict[str, str]) -> None:
    """Refuse to start a non-development installation with default credentials.

    Called before anything touches the database. Checking after seeding meant a
    correctly-refused start still wrote a default-password administrator row —
    the check creating the very hole it exists to close.
    """
    if settings.environment == "development":
        return
    if settings.secret_key.startswith("dev-only"):
        raise InsecureConfiguration(
            "POWERTRACE_SECRET_KEY must be set outside development."
        )
    if not environ.get("POWERTRACE_ADMIN_PASSWORD"):
        raise InsecureConfiguration(
            "POWERTRACE_ADMIN_PASSWORD must be set outside development; refusing to "
            "create an administrator with a default password."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
