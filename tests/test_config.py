from farewatch.config import load_settings


def test_locked_scope():
    settings = load_settings()
    assert settings.origin == "BUD"
    assert settings.dest == "MAD"
    assert settings.horizon_days == 180
    assert settings.currency == "HUF"
    assert settings.direct_only is True
    assert settings.carry_on_bags == 0
    assert settings.source == "google_flights"
    assert len(settings.pinned_trips) == 1
    trip = settings.pinned_trips[0]
    assert trip.outbound_date.isoformat() == "2027-03-12"
    assert trip.return_date.isoformat() == "2027-03-15"
    assert trip.collect_oneways is True
    assert len(settings.pinned_flex) == 1
    flex = settings.pinned_flex[0]
    assert flex.outbound_from.isoformat() == "2027-03-10"
    assert flex.outbound_to.isoformat() == "2027-03-13"
    assert flex.return_from.isoformat() == "2027-03-14"
    assert flex.return_to.isoformat() == "2027-03-17"
    assert len(settings.stay_horizons) == 1
    stay = settings.stay_horizons[0]
    assert stay.origin == "BUD"
    assert stay.dest == "PDL"
    assert stay.horizon_days == 90
    assert stay.stay_nights == 7
    assert stay.max_stops == 1
    assert len(settings.via_probes) == 1
    probe = settings.via_probes[0]
    assert probe.origin == "BUD"
    assert probe.via == "LIS"
    assert probe.dest == "PDL"
    assert probe.stay_nights == 7
    assert probe.max_stops == 0
    assert probe.offsets == (14, 21, 28, 35, 42)
