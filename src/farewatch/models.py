from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class SearchRequest:
    origin: str
    dest: str
    outbound_date: date
    return_date: date | None
    cabin: str
    adults: int
    currency: str
    language: str
    direct_only: bool
    carry_on_bags: int
    checked_bags: int

    @property
    def trip_type(self) -> str:
        return "RT" if self.return_date else "OW"

    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.origin,
            self.dest,
            self.outbound_date.isoformat(),
            self.return_date.isoformat() if self.return_date else "",
            self.trip_type,
        )


@dataclass
class Offer:
    airline: str
    airline_code: str | None
    outbound_flights: str
    return_flights: str
    departure_at: str | None
    arrival_at: str | None
    return_departure_at: str | None
    return_arrival_at: str | None
    stops: int
    is_direct: bool
    duration_minutes: int | None
    price_amount: float
    currency: str
    fare_brand: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass
class SearchResult:
    request: SearchRequest
    offers: list[Offer]
    raw: Any
    fetched_at: datetime
    status: str = "ok"
    error: str | None = None
