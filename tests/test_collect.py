from dataclasses import replace
from datetime import date

from farewatch.collector import collect
from farewatch.config import load_settings
from farewatch.db import connect, status_rows


def _settings(tmp_path):
    base = load_settings()
    return replace(
        base,
        data_dir=tmp_path,
        db_path=tmp_path / "fares.sqlite3",
        raw_dir=tmp_path / "raw",
        reports_dir=tmp_path / "reports",
        backups_dir=tmp_path / "backups",
        docs_dir=tmp_path / "docs",
        request_delay_seconds=0,
        request_jitter_seconds=0,
    )


def test_mock_collect_and_idempotent(tmp_path):
    settings = _settings(tmp_path)
    today = date(2026, 8, 21)
    first = collect(
        settings,
        source_name="mock",
        pinned_only=True,
        today=today,
    )
    assert first.planned == 18
    assert first.ok == 18
    assert first.skipped == 0
    assert first.duration_seconds >= 0
    raw_files = list((tmp_path / "raw").glob("*.json"))
    assert len(raw_files) == 18

    second = collect(
        settings,
        source_name="mock",
        pinned_only=True,
        today=today,
    )
    assert second.skipped == 18
    assert second.ok == 0

    forced = collect(
        settings,
        source_name="mock",
        pinned_only=True,
        today=today,
        force=True,
    )
    assert forced.ok == 18

    conn = connect(settings.db_path)
    try:
        info = status_rows(conn)
        runs = conn.execute(
            "SELECT COUNT(*) AS n, MAX(duration_seconds) AS sec FROM collect_runs"
        ).fetchone()
    finally:
        conn.close()
    assert info["snapshots"] == 18
    assert info["offers"] == 54
    assert info["pinned_recent"]
    assert info["pinned_recent"][0]["min_price"] is not None
    assert runs["n"] == 3
    assert runs["sec"] is not None


def test_retries_error_snapshots_without_force(tmp_path):
    settings = _settings(tmp_path)
    today = date(2026, 8, 21)
    collect(settings, source_name="mock", pinned_only=True, today=today)
    conn = connect(settings.db_path)
    conn.execute("UPDATE snapshots SET status = 'error', error = 'simulated'")
    conn.commit()
    conn.close()

    again = collect(settings, source_name="mock", pinned_only=True, today=today)
    assert again.skipped == 0
    assert again.ok == 18

    conn = connect(settings.db_path)
    try:
        info = status_rows(conn)
    finally:
        conn.close()
    assert info["by_status"].get("ok") == 18
    assert info["by_status"].get("error") is None
