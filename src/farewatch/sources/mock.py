from __future__ import annotations

from datetime import datetime, timezone
from math import sin

from farewatch.models import Offer, SearchRequest, SearchResult
from farewatch.sources.base import SourceAdapter

AIRLINES = (
    ("Wizz Air", "W6"),
    ("Ryanair", "FR"),
    ("Iberia", "IB"),
)


class MockSource(SourceAdapter):
    """Hálózati hívás nélküli forrás teszthez és száraz futtatáshoz."""

    name = "mock"

    def search(self, request: SearchRequest) -> SearchResult:
        days = (request.outbound_date - datetime.now(timezone.utc).date()).days
        offers: list[Offer] = []
        for index, (name, code) in enumerate(AIRLINES):
            wave = 40 * sin((request.outbound_date.toordinal() + index) / 7)
            base = 18000 + index * 4500 + max(0, 70 - days) * 180
            amount = round(base + wave, 0)
            dep_hour = 6 + index * 4
            outbound_at = f"{request.outbound_date.isoformat()}T{dep_hour:02d}:15:00"
            arrival_at = f"{request.outbound_date.isoformat()}T{dep_hour + 3:02d}:35:00"
            return_dep = return_arr = None
            return_flights = ""
            if request.return_date:
                return_dep = f"{request.return_date.isoformat()}T{14 + index:02d}:00:00"
                return_arr = f"{request.return_date.isoformat()}T{17 + index:02d}:20:00"
                return_flights = f"{code}RET"
                amount = round(amount * 1.85, 0)
            offers.append(
                Offer(
                    airline=name,
                    airline_code=code,
                    outbound_flights=f"{code}{2000 + index}",
                    return_flights=return_flights,
                    departure_at=outbound_at,
                    arrival_at=arrival_at,
                    return_departure_at=return_dep,
                    return_arrival_at=return_arr,
                    stops=0 if not request.max_stops else 1,
                    is_direct=not request.max_stops,
                    duration_minutes=200,
                    price_amount=amount,
                    currency=request.currency,
                    fare_brand="basic",
                )
            )
        return SearchResult(
            request=request,
            offers=offers,
            raw={"source": "mock", "days_to_departure": days},
            fetched_at=datetime.now(timezone.utc),
            status="ok",
        )
