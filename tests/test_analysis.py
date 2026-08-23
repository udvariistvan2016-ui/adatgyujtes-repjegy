from dataclasses import replace
from datetime import date

from farewatch.analysis import run_analysis
from farewatch.collector import collect
from farewatch.config import load_settings


def test_analyze_writes_csv(tmp_path):
    settings = replace(
        load_settings(),
        data_dir=tmp_path,
        db_path=tmp_path / "fares.sqlite3",
        raw_dir=tmp_path / "raw",
        reports_dir=tmp_path / "reports",
        backups_dir=tmp_path / "backups",
        docs_dir=tmp_path / "docs",
    )
    collect(settings, source_name="mock", limit=5, today=date(2026, 8, 21))
    result = run_analysis(settings)
    assert result["horizon_rows"] >= 5
    assert result["pinned_rows"] == 1
    assert result["pdl_rows"] == 0
    assert (tmp_path / "reports" / "horizon_min_prices.csv").exists()
    assert (tmp_path / "reports" / "pinned_rt_2027-03-12.csv").exists()
    assert (tmp_path / "reports" / "pdl_rt_7n.csv").exists()
