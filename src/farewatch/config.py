from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_NAME = "config.yaml"


@dataclass(frozen=True)
class PinnedTrip:
    origin: str
    dest: str
    outbound_date: date
    return_date: date
    collect_oneways: bool = True


@dataclass(frozen=True)
class StayHorizon:
    origin: str
    dest: str
    horizon_days: int
    stay_nights: int
    max_stops: int = 1


@dataclass(frozen=True)
class Settings:
    source: str
    origin: str
    dest: str
    horizon_days: int
    cabin: str
    adults: int
    currency: str
    language: str
    timezone: str
    direct_only: bool
    carry_on_bags: int
    checked_bags: int
    request_delay_seconds: float
    request_jitter_seconds: float
    max_retries: int
    collect_hour: str
    pinned_trips: tuple[PinnedTrip, ...]
    stay_horizons: tuple[StayHorizon, ...]
    project_root: Path
    data_dir: Path
    db_path: Path
    raw_dir: Path
    reports_dir: Path
    backups_dir: Path
    docs_dir: Path


def find_project_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / DEFAULT_CONFIG_NAME).exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return here


def _as_date(value: str | date) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def load_settings(config_path: Path | None = None) -> Settings:
    root = find_project_root()
    path = Path(config_path) if config_path else root / DEFAULT_CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(f"Hiányzik a konfiguráció: {path}")

    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pinned = tuple(
        PinnedTrip(
            origin=str(item["origin"]).upper(),
            dest=str(item["dest"]).upper(),
            outbound_date=_as_date(item["outbound_date"]),
            return_date=_as_date(item["return_date"]),
            collect_oneways=bool(item.get("collect_oneways", True)),
        )
        for item in raw.get("pinned_trips") or []
    )
    stay_horizons = tuple(
        StayHorizon(
            origin=str(item["origin"]).upper(),
            dest=str(item["dest"]).upper(),
            horizon_days=int(item.get("horizon_days", 180)),
            stay_nights=int(item["stay_nights"]),
            max_stops=int(item.get("max_stops", 1)),
        )
        for item in raw.get("stay_horizons") or []
    )
    data_dir = root / "data"
    return Settings(
        source=str(raw.get("source", "google_flights")),
        origin=str(raw.get("origin", "BUD")).upper(),
        dest=str(raw.get("dest", "MAD")).upper(),
        horizon_days=int(raw.get("horizon_days", 180)),
        cabin=str(raw.get("cabin", "economy")),
        adults=int(raw.get("adults", 1)),
        currency=str(raw.get("currency", "HUF")).upper(),
        language=str(raw.get("language", "hu")),
        timezone=str(raw.get("timezone", "Europe/Budapest")),
        direct_only=bool(raw.get("direct_only", True)),
        carry_on_bags=int(raw.get("carry_on_bags", 0)),
        checked_bags=int(raw.get("checked_bags", 0)),
        request_delay_seconds=float(raw.get("request_delay_seconds", 2.5)),
        request_jitter_seconds=float(raw.get("request_jitter_seconds", 0.8)),
        max_retries=int(raw.get("max_retries", 3)),
        collect_hour=str(raw.get("collect_hour", "06:00")),
        pinned_trips=pinned,
        stay_horizons=stay_horizons,
        project_root=root,
        data_dir=data_dir,
        db_path=data_dir / "fares.sqlite3",
        raw_dir=data_dir / "raw",
        reports_dir=data_dir / "reports",
        backups_dir=data_dir / "backups",
        docs_dir=root / "docs",
    )
