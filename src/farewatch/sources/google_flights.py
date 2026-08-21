from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from farewatch.models import Offer, SearchRequest, SearchResult
from farewatch.sources.base import SourceAdapter

AIRLINE_CODES = {
    "wizz air": "W6",
    "wizz": "W6",
    "ryanair": "FR",
    "iberia": "IB",
    "iberia express": "I2",
}

# Nyilvános, nem személyes Google consent sütik — EU-ban a kereső consent.google.com-ra
# irányít cookie nélkül, és a fast-flights parser ilyenkor összeomlik.
_CONSENT_COOKIE = (
    "CONSENT=YES+cb.20210328-17-p0.en+FX+410; "
    "SOCS=CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjQwMzA1LjA1X3AwGgJlbiACGgYIgL_XswY"
)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _jsonable(val) for key, val in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _fmt_dt(simple: Any) -> str | None:
    if simple is None:
        return None
    date_part = getattr(simple, "date", None)
    time_part = getattr(simple, "time", None)
    if not date_part or not time_part:
        return None
    year, month, day = date_part
    hour, minute = time_part
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"


def _airline_code(name: str) -> str | None:
    return AIRLINE_CODES.get(name.strip().lower())


def _split_legs(segments: list[Any], dest: str, has_return: bool) -> tuple[list[Any], list[Any]]:
    if not has_return:
        return list(segments), []
    outbound: list[Any] = []
    inbound: list[Any] = []
    reached = False
    for segment in segments:
        if not reached:
            outbound.append(segment)
            to_airport = getattr(getattr(segment, "to_airport", None), "code", "")
            if str(to_airport).upper() == dest:
                reached = True
        else:
            inbound.append(segment)
    if not inbound and len(segments) >= 2:
        outbound, inbound = [segments[0]], list(segments[1:])
    return outbound, inbound


def map_flights(request: SearchRequest, items: list[Any]) -> list[Offer]:
    offers: list[Offer] = []
    for item in items:
        segments = list(getattr(item, "flights", []) or [])
        outbound, inbound = _split_legs(segments, request.dest, request.return_date is not None)
        airlines = [str(name) for name in (getattr(item, "airlines", None) or []) if name]
        airline = airlines[0] if airlines else "unknown"
        out_stops = max(len(outbound) - 1, 0)
        in_stops = max(len(inbound) - 1, 0) if inbound else 0
        stops = out_stops + in_stops
        is_direct = out_stops == 0 and (not inbound or in_stops == 0)
        if request.direct_only and not is_direct:
            continue
        duration = sum(int(getattr(seg, "duration", 0) or 0) for seg in outbound + inbound) or None
        first_out = outbound[0] if outbound else None
        last_out = outbound[-1] if outbound else None
        first_in = inbound[0] if inbound else None
        last_in = inbound[-1] if inbound else None
        price = getattr(item, "price", None)
        if price is None:
            continue
        offers.append(
            Offer(
                airline=airline,
                airline_code=_airline_code(airline),
                outbound_flights="+".join(airlines) if airlines else "",
                return_flights="+".join(airlines[1:]) if request.return_date and len(airlines) > 1 else "",
                departure_at=_fmt_dt(getattr(first_out, "departure", None) if first_out else None),
                arrival_at=_fmt_dt(getattr(last_out, "arrival", None) if last_out else None),
                return_departure_at=_fmt_dt(getattr(first_in, "departure", None) if first_in else None),
                return_arrival_at=_fmt_dt(getattr(last_in, "arrival", None) if last_in else None),
                stops=stops,
                is_direct=is_direct,
                duration_minutes=duration,
                price_amount=float(price),
                currency=request.currency,
                fare_brand="basic",
                extra={"type": getattr(item, "type", None), "airlines": airlines},
            )
        )
    return offers


def _build_query(request: SearchRequest):
    from fast_flights import FlightQuery, Passengers, create_query

    legs = [
        FlightQuery(
            date=request.outbound_date.isoformat(),
            from_airport=request.origin,
            to_airport=request.dest,
            max_stops=0 if request.direct_only else None,
        )
    ]
    trip = "one-way"
    if request.return_date:
        legs.append(
            FlightQuery(
                date=request.return_date.isoformat(),
                from_airport=request.dest,
                to_airport=request.origin,
                max_stops=0 if request.direct_only else None,
            )
        )
        trip = "round-trip"

    return create_query(
        flights=legs,
        seat=request.cabin,  # type: ignore[arg-type]
        trip=trip,  # type: ignore[arg-type]
        passengers=Passengers(adults=request.adults),
        language=request.language or "en-US",
        currency=request.currency,  # type: ignore[arg-type]
        max_stops=0 if request.direct_only else None,
        carry_on_bags=request.carry_on_bags,
        checked_bags=request.checked_bags,
        hide_separate_and_self_transfer=True,
        exclude_basic_economy=False,
    )


def fetch_html(query) -> str:
    from primp import Client

    client = Client(
        impersonate="chrome_145",
        impersonate_os="windows",
        referer=True,
        cookie_store=True,
    )
    response = client.get(
        "https://www.google.com/travel/flights",
        params=query.params(),
        headers={"Cookie": _CONSENT_COOKIE},
    )
    return response.text


class GoogleFlightsSource(SourceAdapter):
    """Google Flights a fast-flights könyvtáron (nyilvános keresőoldal)."""

    name = "google_flights"

    def search(self, request: SearchRequest) -> SearchResult:
        from fast_flights import FlightsNotFound
        from fast_flights.parser import parse

        fetched_at = datetime.now(timezone.utc)
        html = ""
        try:
            query = _build_query(request)
            html = fetch_html(query)
            if "consent.google.com" in html:
                return SearchResult(
                    request=request,
                    offers=[],
                    raw={"error": "google_consent_redirect", "html_len": len(html)},
                    fetched_at=fetched_at,
                    status="error",
                    error="Google consent page (EU cookie wall)",
                )
            result_list = parse(html)
        except FlightsNotFound:
            return SearchResult(
                request=request,
                offers=[],
                raw={"error": "FlightsNotFound", "html_len": len(html)},
                fetched_at=fetched_at,
                status="empty",
                error="no flights",
            )
        except Exception as exc:  # noqa: BLE001 — forrás törékeny, a napi futás ne álljon le
            return SearchResult(
                request=request,
                offers=[],
                raw={
                    "error": str(exc),
                    "html_len": len(html),
                    "html_head": html[:1500],
                },
                fetched_at=fetched_at,
                status="error",
                error=str(exc),
            )

        items = list(result_list)
        offers = map_flights(request, items)
        status = "ok" if offers else "empty"
        return SearchResult(
            request=request,
            offers=offers,
            raw=_jsonable(items),
            fetched_at=fetched_at,
            status=status,
            error=None if offers else "parsed zero offers",
        )
