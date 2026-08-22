from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from farewatch.models import Offer, SearchRequest, SearchResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    collected_at TEXT NOT NULL,
    collected_on TEXT NOT NULL,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    outbound_date TEXT NOT NULL,
    return_date TEXT NOT NULL DEFAULT '',
    trip_type TEXT NOT NULL,
    cabin TEXT NOT NULL,
    adults INTEGER NOT NULL,
    currency TEXT NOT NULL,
    source TEXT NOT NULL,
    direct_only INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    offer_count INTEGER NOT NULL DEFAULT 0,
    raw_path TEXT,
    UNIQUE (collected_on, origin, dest, outbound_date, return_date, source, trip_type)
);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    airline TEXT,
    airline_code TEXT,
    outbound_flights TEXT,
    return_flights TEXT,
    departure_at TEXT,
    arrival_at TEXT,
    return_departure_at TEXT,
    return_arrival_at TEXT,
    stops INTEGER NOT NULL DEFAULT 0,
    is_direct INTEGER NOT NULL DEFAULT 1,
    duration_minutes INTEGER,
    price_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    fare_brand TEXT,
    extra_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_offers_snapshot ON offers(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_collected ON snapshots(collected_on);
CREATE INDEX IF NOT EXISTS idx_snapshots_route ON snapshots(origin, dest, trip_type);

CREATE TABLE IF NOT EXISTS collect_runs (
    id INTEGER PRIMARY KEY,
    collected_on TEXT NOT NULL,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    planned INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    empty INTEGER NOT NULL,
    error INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_collect_runs_day ON collect_runs(collected_on, source);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


def existing_snapshot(
    conn: sqlite3.Connection,
    *,
    collected_on: date,
    request: SearchRequest,
    source: str,
) -> tuple[int, str] | None:
    row = conn.execute(
        """
        SELECT id, status FROM snapshots
        WHERE collected_on = ?
          AND origin = ?
          AND dest = ?
          AND outbound_date = ?
          AND return_date = ?
          AND source = ?
          AND trip_type = ?
        """,
        (
            collected_on.isoformat(),
            request.origin,
            request.dest,
            request.outbound_date.isoformat(),
            request.return_date.isoformat() if request.return_date else "",
            source,
            request.trip_type,
        ),
    ).fetchone()
    if not row:
        return None
    return int(row["id"]), str(row["status"])


def existing_snapshot_id(
    conn: sqlite3.Connection,
    *,
    collected_on: date,
    request: SearchRequest,
    source: str,
) -> int | None:
    found = existing_snapshot(
        conn, collected_on=collected_on, request=request, source=source
    )
    return found[0] if found else None


def save_result(
    conn: sqlite3.Connection,
    *,
    collected_on: date,
    source: str,
    result: SearchResult,
    raw_path: str | None,
    replace_id: int | None = None,
) -> int:
    request = result.request
    return_date = request.return_date.isoformat() if request.return_date else ""
    payload = (
        result.fetched_at.replace(microsecond=0).isoformat(),
        collected_on.isoformat(),
        request.origin,
        request.dest,
        request.outbound_date.isoformat(),
        return_date,
        request.trip_type,
        request.cabin,
        request.adults,
        request.currency,
        source,
        int(request.direct_only),
        result.status,
        result.error,
        len(result.offers),
        raw_path,
    )
    if replace_id is not None:
        conn.execute("DELETE FROM offers WHERE snapshot_id = ?", (replace_id,))
        conn.execute(
            """
            UPDATE snapshots SET
                collected_at=?, collected_on=?, origin=?, dest=?, outbound_date=?,
                return_date=?, trip_type=?, cabin=?, adults=?, currency=?, source=?,
                direct_only=?, status=?, error=?, offer_count=?, raw_path=?
            WHERE id=?
            """,
            (*payload, replace_id),
        )
        snapshot_id = replace_id
    else:
        cursor = conn.execute(
            """
            INSERT INTO snapshots (
                collected_at, collected_on, origin, dest, outbound_date, return_date,
                trip_type, cabin, adults, currency, source, direct_only, status, error,
                offer_count, raw_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        snapshot_id = int(cursor.lastrowid)

    rows: Iterable[tuple[Any, ...]] = (
        (
            snapshot_id,
            offer.airline,
            offer.airline_code,
            offer.outbound_flights,
            offer.return_flights,
            offer.departure_at,
            offer.arrival_at,
            offer.return_departure_at,
            offer.return_arrival_at,
            offer.stops,
            int(offer.is_direct),
            offer.duration_minutes,
            offer.price_amount,
            offer.currency,
            offer.fare_brand,
            json.dumps(offer.extra, ensure_ascii=False, default=str),
        )
        for offer in result.offers
    )
    conn.executemany(
        """
        INSERT INTO offers (
            snapshot_id, airline, airline_code, outbound_flights, return_flights,
            departure_at, arrival_at, return_departure_at, return_arrival_at,
            stops, is_direct, duration_minutes, price_amount, currency, fare_brand,
            extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        list(rows),
    )
    conn.commit()
    return snapshot_id


def save_collect_run(
    conn: sqlite3.Connection,
    *,
    collected_on: date,
    source: str,
    started_at: datetime,
    finished_at: datetime,
    duration_seconds: float,
    planned: int,
    skipped: int,
    ok: int,
    empty: int,
    error: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO collect_runs (
            collected_on, source, started_at, finished_at, duration_seconds,
            planned, skipped, ok, empty, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            collected_on.isoformat(),
            source,
            started_at.replace(microsecond=0).isoformat(),
            finished_at.replace(microsecond=0).isoformat(),
            float(duration_seconds),
            planned,
            skipped,
            ok,
            empty,
            error,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def status_rows(conn: sqlite3.Connection) -> dict[str, Any]:
    snapshot_count = conn.execute("SELECT COUNT(*) AS n FROM snapshots").fetchone()["n"]
    offer_count = conn.execute("SELECT COUNT(*) AS n FROM offers").fetchone()["n"]
    by_status = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM snapshots GROUP BY status"
        )
    }
    latest = conn.execute(
        "SELECT MAX(collected_on) AS d FROM snapshots"
    ).fetchone()["d"]
    pinned = conn.execute(
        """
        SELECT s.collected_on, s.status, s.offer_count,
               MIN(o.price_amount) AS min_price, o.currency
        FROM snapshots s
        LEFT JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'RT'
          AND s.outbound_date = '2027-03-12'
          AND s.return_date = '2027-03-15'
        GROUP BY s.id
        ORDER BY s.collected_on DESC
        LIMIT 8
        """
    ).fetchall()
    return {
        "snapshots": snapshot_count,
        "offers": offer_count,
        "by_status": by_status,
        "latest_collected_on": latest,
        "pinned_recent": [dict(row) for row in pinned],
    }
