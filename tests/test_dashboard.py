from datetime import date

from farewatch.collector import collect
from farewatch.dashboard import write_dashboard
from farewatch.config import load_settings
from dataclasses import replace


def test_dashboard_marks_errors_and_writes_html(tmp_path):
    settings = replace(
        load_settings(),
        data_dir=tmp_path,
        db_path=tmp_path / "fares.sqlite3",
        raw_dir=tmp_path / "raw",
        reports_dir=tmp_path / "reports",
        backups_dir=tmp_path / "backups",
        docs_dir=tmp_path / "docs",
    )
    collect(settings, source_name="mock", pinned_only=True, today=date(2026, 8, 21))
    path = write_dashboard(settings, today=date(2026, 8, 21))
    html = path.read_text(encoding="utf-8")
    assert "BUD" in html
    assert "2027-03-12" in html or "márc" in html
    assert '"kind": "ok"' in html or '"kind":"ok"' in html
    assert "oda-vissza (RT)" in html or "oda-vissza" in html
    assert '"date": "2026-08-21"' in html
    assert '"date": "2026-07-22"' not in html
    assert (tmp_path / "docs" / ".nojekyll").exists()
