from __future__ import annotations

import json
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
    "tap air portugal": "TP",
    "tap portugal": "TP",
    "tap": "TP",
    "azores airlines": "S4",
    "sata": "S4",
    "sata air acores": "S4",
    "sata internacional": "S4",
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


def _effective_max_stops(request: SearchRequest) -> int | None:
    if request.max_stops is not None:
        return request.max_stops
    return 0 if request.direct_only else None


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


def flight_codes_from_html(html: str) -> list[list[str]]:
    """A fast-flights parser eldobja; a Google JS 22-es mezője: ['W6', '2371', None, 'Wizz Air']."""
    try:
        from selectolax.lexbor import LexborHTMLParser

        script = LexborHTMLParser(html).css_first(r"script.ds\:1")
        if script is None:
            return []
        blob = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
        if blob.endswith("errorHasStatus: true"):
            return []
        rows = json.loads(blob)[3][0]
        if not rows:
            return []
        codes: list[list[str]] = []
        for row in rows:
            found: list[str] = []
            for segment in row[0][2]:
                info = segment[22] if len(segment) > 22 else None
                if isinstance(info, list) and len(info) >= 2 and info[0] and info[1]:
                    found.append(f"{info[0]} {info[1]}")
            codes.append(found)
        return codes
    except Exception:  # noqa: BLE001 — járatszám opcionális
        return []


def map_flights(
    request: SearchRequest,
    items: list[Any],
    flight_codes: list[list[str]] | None = None,
) -> list[Offer]:
    offers: list[Offer] = []
    for index, item in enumerate(items):
        segments = list(getattr(item, "flights", []) or [])
        outbound, inbound = _split_legs(segments, request.dest, request.return_date is not None)
        airlines = [str(name) for name in (getattr(item, "airlines", None) or []) if name]
        airline = airlines[0] if airlines else "unknown"
        out_stops = max(len(outbound) - 1, 0)
        in_stops = max(len(inbound) - 1, 0) if inbound else 0
        stops = max(out_stops, in_stops)
        is_direct = out_stops == 0 and (not inbound or in_stops == 0)
        limit = _effective_max_stops(request)
        if limit is not None and (out_stops > limit or (inbound and in_stops > limit)):
            continue
        duration = sum(int(getattr(seg, "duration", 0) or 0) for seg in outbound + inbound) or None
        first_out = outbound[0] if outbound else None
        last_out = outbound[-1] if outbound else None
        first_in = inbound[0] if inbound else None
        last_in = inbound[-1] if inbound else None
        price = getattr(item, "price", None)
        if price is None:
            continue
        codes = flight_codes[index] if flight_codes and index < len(flight_codes) else []
        out_code = codes[0] if codes else ""
        in_code = ""
        if request.return_date and len(codes) > len(outbound):
            in_code = codes[len(outbound)]
        elif request.return_date and len(codes) > 1:
            in_code = codes[1]
        offers.append(
            Offer(
                airline=airline,
                airline_code=_airline_code(airline),
                outbound_flights=out_code or "+".join(airlines) if airlines else out_code,
                return_flights=in_code,
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
                extra={
                    "type": getattr(item, "type", None),
                    "airlines": airlines,
                    "plane_type": getattr(first_out, "plane_type", None),
                    "return_plane_type": getattr(first_in, "plane_type", None) if first_in else None,
                    "out_stops": out_stops,
                    "in_stops": in_stops,
                },
            )
        )
    return offers


def _build_query(request: SearchRequest):
    from fast_flights import FlightQuery, Passengers, create_query

    max_stops = _effective_max_stops(request)
    legs = [
        FlightQuery(
            date=request.outbound_date.isoformat(),
            from_airport=request.origin,
            to_airport=request.dest,
            max_stops=max_stops,
        )
    ]
    trip = "one-way"
    if request.return_date:
        legs.append(
            FlightQuery(
                date=request.return_date.isoformat(),
                from_airport=request.dest,
                to_airport=request.origin,
                max_stops=max_stops,
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
        max_stops=max_stops,
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
        offers = map_flights(request, items, flight_codes=flight_codes_from_html(html))
        status = "ok" if offers else "empty"
        return SearchResult(
            request=request,
            offers=offers,
            raw=_jsonable(items),
            fetched_at=fetched_at,
            status=status,
            error=None if offers else "parsed zero offers",
        )
