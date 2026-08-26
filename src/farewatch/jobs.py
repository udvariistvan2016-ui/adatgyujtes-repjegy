from __future__ import annotations

from datetime import date, timedelta

from farewatch.config import PinnedFlex, Settings
from farewatch.models import SearchRequest

SCOPES = ("mad", "stay", "probe")


def date_span(start: date, end: date) -> list[date]:
    if end < start:
        return []
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def flex_rt_pairs(flex: PinnedFlex) -> list[tuple[date, date]]:
    pairs: list[tuple[date, date]] = []
    for outbound in date_span(flex.outbound_from, flex.outbound_to):
        for inbound in date_span(flex.return_from, flex.return_to):
            if inbound > outbound:
                pairs.append((outbound, inbound))
    return pairs


def horizon_dates(today: date, horizon_days: int) -> list[date]:
    """Ma-tól számított 180 nap: today, today+1, …, today+horizon_days-1."""
    if horizon_days < 1:
        return []
    return [today + timedelta(days=offset) for offset in range(horizon_days)]


def build_jobs(
    settings: Settings,
    today: date,
    *,
    limit: int | None = None,
    pinned_only: bool = False,
    only_date: date | None = None,
    scope: str = "mad",
) -> list[SearchRequest]:
    if scope not in SCOPES:
        raise ValueError(f"Ismeretlen scope: {scope}. Elérhető: {', '.join(SCOPES)}")

    jobs: list[SearchRequest] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    def add(req: SearchRequest) -> None:
        key = req.key()
        if key in seen:
            return
        seen.add(key)
        jobs.append(req)

    def base(**overrides: object) -> SearchRequest:
        values = dict(
            origin=settings.origin,
            dest=settings.dest,
            cabin=settings.cabin,
            adults=settings.adults,
            currency=settings.currency,
            language=settings.language,
            direct_only=settings.direct_only,
            carry_on_bags=settings.carry_on_bags,
            checked_bags=settings.checked_bags,
            max_stops=0 if settings.direct_only else None,
        )
        values.update(overrides)
        return SearchRequest(**values)  # type: ignore[arg-type]

    if scope == "probe":
        if pinned_only:
            return []
        for probe in settings.via_probes:
            dates = [today + timedelta(days=offset) for offset in probe.offsets]
            if only_date is not None:
                dates = [day for day in dates if day == only_date]
            if limit is not None:
                dates = dates[:limit]
            for outbound in dates:
                inbound = outbound + timedelta(days=probe.stay_nights)
                legs = (
                    (probe.origin, probe.via, outbound),
                    (probe.via, probe.dest, outbound),
                    (probe.dest, probe.via, inbound),
                    (probe.via, probe.origin, inbound),
                )
                for origin, dest, day in legs:
                    add(
                        base(
                            origin=origin,
                            dest=dest,
                            outbound_date=day,
                            return_date=None,
                            direct_only=probe.max_stops == 0,
                            max_stops=probe.max_stops,
                        )
                    )
        return jobs

    if scope == "stay":
        if pinned_only:
            return []
        for horizon in settings.stay_horizons:
            dates = horizon_dates(today, horizon.horizon_days)
            if only_date is not None:
                dates = [d for d in dates if d == only_date]
            if limit is not None:
                dates = dates[:limit]
            for outbound in dates:
                add(
                    base(
                        origin=horizon.origin,
                        dest=horizon.dest,
                        outbound_date=outbound,
                        return_date=outbound + timedelta(days=horizon.stay_nights),
                        direct_only=horizon.max_stops == 0,
                        max_stops=horizon.max_stops,
                    )
                )
        return jobs

    if not pinned_only:
        dates = horizon_dates(today, settings.horizon_days)
        if only_date is not None:
            dates = [d for d in dates if d == only_date]
        if limit is not None:
            dates = dates[:limit]
        for outbound in dates:
            add(base(outbound_date=outbound, return_date=None))

    for trip in settings.pinned_trips:
        if trip.outbound_date < today:
            continue
        add(
            base(
                origin=trip.origin,
                dest=trip.dest,
                outbound_date=trip.outbound_date,
                return_date=trip.return_date,
            )
        )
        if trip.collect_oneways:
            add(
                base(
                    origin=trip.origin,
                    dest=trip.dest,
                    outbound_date=trip.outbound_date,
                    return_date=None,
                )
            )
            add(
                base(
                    origin=trip.dest,
                    dest=trip.origin,
                    outbound_date=trip.return_date,
                    return_date=None,
                )
            )

    for flex in settings.pinned_flex:
        for outbound, inbound in flex_rt_pairs(flex):
            if outbound < today:
                continue
            add(
                base(
                    origin=flex.origin,
                    dest=flex.dest,
                    outbound_date=outbound,
                    return_date=inbound,
                )
            )

    return jobs
