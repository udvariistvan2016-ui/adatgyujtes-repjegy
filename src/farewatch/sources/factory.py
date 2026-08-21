from __future__ import annotations

from farewatch.sources import SourceAdapter
from farewatch.sources.google_flights import GoogleFlightsSource
from farewatch.sources.mock import MockSource

ADAPTERS = {
    "google_flights": GoogleFlightsSource,
    "mock": MockSource,
}


def get_adapter(name: str) -> SourceAdapter:
    try:
        return ADAPTERS[name]()
    except KeyError as exc:
        known = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"Ismeretlen forrás: {name}. Elérhető: {known}") from exc
