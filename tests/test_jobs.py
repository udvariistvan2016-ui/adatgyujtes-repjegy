from datetime import date, timedelta

from farewatch.config import load_settings
from farewatch.jobs import build_jobs, flex_rt_pairs, horizon_dates


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
    assert ("BUD", "MAD", date(2027, 3, 10), date(2027, 3, 14)) in origins
    assert len(rt) == 16
    assert len(jobs) == 198


def test_pinned_only():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), pinned_only=True)
    assert len(jobs) == 18
    assert sum(1 for j in jobs if j.trip_type == "RT") == 16
    assert {j.trip_type for j in jobs} == {"OW", "RT"}


def test_flex_grid_is_sixteen_unique_rt():
    settings = load_settings()
    pairs = flex_rt_pairs(settings.pinned_flex[0])
    assert len(pairs) == 16
    assert (date(2027, 3, 12), date(2027, 3, 15)) in pairs
    assert len(set(pairs)) == 16


def test_limit_does_not_drop_pinned():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), limit=2)
    assert sum(1 for j in jobs if j.trip_type == "OW" and j.origin == "BUD" and j.outbound_date <= date(2026, 8, 22)) == 2
    assert any(j.trip_type == "RT" for j in jobs)


def test_mad_scope_excludes_pdl():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), scope="mad")
    assert all(j.dest != "PDL" for j in jobs)
    assert len(jobs) == 198


def test_stay_scope_pdl_rt():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), scope="stay")
    assert len(jobs) == 90
    assert all(j.origin == "BUD" and j.dest == "PDL" for j in jobs)
    assert all(j.trip_type == "RT" for j in jobs)
    assert all(j.return_date == j.outbound_date + timedelta(days=7) for j in jobs)
    assert all(j.max_stops == 1 for j in jobs)
    assert all(j.direct_only is False for j in jobs)


def test_pinned_only_stay_is_empty():
    settings = load_settings()
    jobs = build_jobs(settings, date(2026, 8, 21), pinned_only=True, scope="stay")
    assert jobs == []


def test_probe_scope_four_legs():
    settings = load_settings()
    today = date(2026, 8, 21)
    jobs = build_jobs(settings, today, scope="probe")
    assert len(jobs) == 20
    assert all(j.trip_type == "OW" for j in jobs)
    assert all(j.max_stops == 0 for j in jobs)
    first = today + timedelta(days=14)
    back = first + timedelta(days=7)
    pairs = {(j.origin, j.dest, j.outbound_date) for j in jobs}
    assert ("BUD", "LIS", first) in pairs
    assert ("LIS", "PDL", first) in pairs
    assert ("PDL", "LIS", back) in pairs
    assert ("LIS", "BUD", back) in pairs
    assert all(j.dest != "MAD" for j in jobs)
    assert not any(j.origin == "BUD" and j.dest == "PDL" for j in jobs)


def test_mad_and_stay_ignore_probe_legs():
    settings = load_settings()
    mad = build_jobs(settings, date(2026, 8, 21), scope="mad")
    stay = build_jobs(settings, date(2026, 8, 21), scope="stay")
    assert all(j.dest != "LIS" and j.origin != "LIS" for j in mad)
    assert all(j.origin == "BUD" and j.dest == "PDL" for j in stay)
