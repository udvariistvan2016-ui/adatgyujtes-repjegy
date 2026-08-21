from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from farewatch.models import SearchRequest
from farewatch.sources.google_flights import map_flights


def _request(**kwargs) -> SearchRequest:
    values = dict(
        origin="BUD",
        dest="MAD",
        outbound_date=date(2027, 3, 12),
        return_date=None,
        cabin="economy",
        adults=1,
        currency="HUF",
        language="hu",
        direct_only=True,
        carry_on_bags=0,
        checked_bags=0,
    )
    values.update(kwargs)
    return SearchRequest(**values)


def _seg(from_code, to_code, day, hour):
    return SimpleNamespace(
        from_airport=SimpleNamespace(code=from_code),
        to_airport=SimpleNamespace(code=to_code),
        departure=SimpleNamespace(date=(2027, 3, day), time=(hour, 0)),
        arrival=SimpleNamespace(date=(2027, 3, day), time=(hour + 3, 20)),
        duration=200,
    )


def test_map_one_way_direct():
    item = SimpleNamespace(
        type="Wizz Air",
        price=19990,
        airlines=["Wizz Air"],
        flights=[_seg("BUD", "MAD", 12, 14)],
    )
    offers = map_flights(_request(), [item])
    assert len(offers) == 1
    assert offers[0].airline_code == "W6"
    assert offers[0].is_direct is True
    assert offers[0].price_amount == 19990
    assert offers[0].departure_at == "2027-03-12T14:00:00"


def test_map_skips_connecting_when_direct_only():
    item = SimpleNamespace(
        type="multi",
        price=15000,
        airlines=["Lufthansa"],
        flights=[_seg("BUD", "MUC", 12, 8), _seg("MUC", "MAD", 12, 12)],
    )
    offers = map_flights(_request(direct_only=True), [item])
    assert offers == []


def test_map_round_trip_splits_legs():
    item = SimpleNamespace(
        type="Wizz Air",
        price=42000,
        airlines=["Wizz Air"],
        flights=[_seg("BUD", "MAD", 12, 6), _seg("MAD", "BUD", 15, 16)],
    )
    request = _request(return_date=date(2027, 3, 15))
    offers = map_flights(request, [item])
    assert len(offers) == 1
    assert offers[0].is_direct is True
    assert offers[0].return_departure_at == "2027-03-15T16:00:00"
