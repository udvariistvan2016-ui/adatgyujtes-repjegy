from datetime import date

from farewatch.config import load_settings
from farewatch.jobs import build_jobs, horizon_dates


def test_horizon_length():
    days = horizon_dates(date(2026, 8, 21), 180)
    assert len(days) == 180
    assert days[0] == date(2026, 8, 21)
    assert days[-1] == date(2027, 2, 16)


def test_jobs_include_horizon_and_pinned():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21))
    ow = [j for j in jobs if j.trip_type == "OW"]
    rt = [j for j in jobs if j.trip_type == "RT"]
    assert len(ow) == 182  # 180 horizont + 03-12 oda + 03-15 vissza (ellenkező irány)
    # Mar 12 BUD-MAD is outside the 180-day window, so collect_oneways adds it.
    origins = {(j.origin, j.dest, j.outbound_date, j.return_date) for j in jobs}
    assert ("BUD", "MAD", date(2026, 8, 21), None) in origins
    assert ("BUD", "MAD", date(2027, 3, 12), date(2027, 3, 15)) in origins
    assert ("BUD", "MAD", date(2027, 3, 12), None) in origins
    assert ("MAD", "BUD", date(2027, 3, 15), None) in origins
    assert len(rt) == 1
    assert len(jobs) == 183


def test_pinned_only():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), pinned_only=True)
    assert len(jobs) == 3
    assert {j.trip_type for j in jobs} == {"OW", "RT"}


def test_limit_does_not_drop_pinned():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), limit=2)
    assert sum(1 for j in jobs if j.trip_type == "OW" and j.origin == "BUD" and j.outbound_date <= date(2026, 8, 22)) == 2
    assert any(j.trip_type == "RT" for j in jobs)
