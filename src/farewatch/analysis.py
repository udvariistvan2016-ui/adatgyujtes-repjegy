from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from farewatch.config import Settings
from farewatch.db import connect


def _ensure_reports(settings: Settings) -> Path:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    return settings.reports_dir


def export_horizon_csv(conn: sqlite3.Connection, path: Path) -> int:
    rows = conn.execute(
        """
        SELECT
            s.collected_on,
            s.outbound_date,
            CAST(julianday(s.outbound_date) - julianday(s.collected_on) AS INT)
                AS days_to_departure,
            MIN(o.price_amount) AS min_price,
            o.currency,
            s.origin,
            s.dest
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'OW'
          AND s.status = 'ok'
        GROUP BY s.id
        ORDER BY s.collected_on, s.outbound_date
        """
    ).fetchall()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "collected_on",
                "outbound_date",
                "days_to_departure",
                "min_price",
                "currency",
                "origin",
                "dest",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return len(rows)


def export_pinned_csv(conn: sqlite3.Connection, path: Path) -> int:
    rows = conn.execute(
        """
        SELECT
            s.collected_on,
            CAST(julianday(s.outbound_date) - julianday(s.collected_on) AS INT)
                AS days_to_departure,
            MIN(o.price_amount) AS min_price,
            o.currency,
            GROUP_CONCAT(o.airline, ' | ') AS airlines
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'RT'
          AND s.outbound_date = '2027-03-12'
          AND s.return_date = '2027-03-15'
          AND s.status = 'ok'
        GROUP BY s.id
        ORDER BY s.collected_on
        """
    ).fetchall()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["collected_on", "days_to_departure", "min_price", "currency", "airlines"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return len(rows)


def _plot_horizon(conn: sqlite3.Connection, path: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    rows = conn.execute(
        """
        SELECT
            CAST(julianday(s.outbound_date) - julianday(s.collected_on) AS INT)
                AS days_to_departure,
            MIN(o.price_amount) AS min_price
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'OW' AND s.status = 'ok'
        GROUP BY s.id
        """
    ).fetchall()
    if not rows:
        return False
    buckets: dict[int, list[float]] = {}
    for row in rows:
        buckets.setdefault(int(row["days_to_departure"]), []).append(float(row["min_price"]))
    xs = sorted(buckets)
    ys = [sorted(buckets[x])[len(buckets[x]) // 2] for x in xs]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(xs, ys, color="#1d4ed8", linewidth=2)
    ax.set_xlabel("Indulásig hátralévő napok")
    ax.set_ylabel("Medián napi minimumár")
    ax.set_title("BUD–MAD egyirányú: ár vs. foglalási ablak")
    ax.invert_xaxis()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True


def _plot_pinned(conn: sqlite3.Connection, path: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    rows = conn.execute(
        """
        SELECT s.collected_on, MIN(o.price_amount) AS min_price
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'RT'
          AND s.outbound_date = '2027-03-12'
          AND s.return_date = '2027-03-15'
          AND s.status = 'ok'
        GROUP BY s.id
        ORDER BY s.collected_on
        """
    ).fetchall()
    if not rows:
        return False
    from datetime import date as date_cls

    xs = [date_cls.fromisoformat(str(row["collected_on"])) for row in rows]
    ys = [float(row["min_price"]) for row in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(xs, ys, marker="o", color="#b45309", linewidth=2)
    ax.set_xlabel("Gyűjtés napja")
    ax.set_ylabel("RT minimumár")
    ax.set_title("Kitűzött út: 2027-03-12 / 03-15")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True


def run_analysis(settings: Settings) -> dict[str, str | int | bool]:
    reports = _ensure_reports(settings)
    conn = connect(settings.db_path)
    try:
        horizon_csv = reports / "horizon_min_prices.csv"
        pinned_csv = reports / "pinned_rt_2027-03-12.csv"
        horizon_png = reports / "horizon_price_vs_days.png"
        pinned_png = reports / "pinned_rt_timeseries.png"
        return {
            "horizon_rows": export_horizon_csv(conn, horizon_csv),
            "pinned_rows": export_pinned_csv(conn, pinned_csv),
            "horizon_csv": str(horizon_csv),
            "pinned_csv": str(pinned_csv),
            "horizon_plot": _plot_horizon(conn, horizon_png),
            "pinned_plot": _plot_pinned(conn, pinned_png),
            "horizon_png": str(horizon_png),
            "pinned_png": str(pinned_png),
        }
    finally:
        conn.close()
