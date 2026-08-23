from __future__ import annotations

from datetime import date, timedelta

from farewatch.config import Settings
from farewatch.models import SearchRequest

SCOPES = ("mad", "stay")


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

    return jobs
