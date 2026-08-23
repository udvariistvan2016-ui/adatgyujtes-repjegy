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
    assert len(settings.stay_horizons) == 1
    stay = settings.stay_horizons[0]
    assert stay.origin == "BUD"
    assert stay.dest == "PDL"
    assert stay.horizon_days == 180
    assert stay.stay_nights == 7
    assert stay.max_stops == 1
