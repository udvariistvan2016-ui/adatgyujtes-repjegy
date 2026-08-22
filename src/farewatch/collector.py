from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from farewatch.config import Settings
from farewatch.db import connect, existing_snapshot, save_collect_run, save_result
from farewatch.jobs import build_jobs
from farewatch.models import SearchRequest, SearchResult
from farewatch.sources.factory import get_adapter

logger = logging.getLogger(__name__)


@dataclass
class CollectSummary:
    planned: int = 0
    skipped: int = 0
    ok: int = 0
    empty: int = 0
    error: int = 0
    duration_seconds: float = 0.0


def today_in_tz(timezone_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except Exception:
        return datetime.now().astimezone().date()


def _write_raw(raw_dir: Path, collected_on: date, request: SearchRequest, raw: object) -> str:
    raw_dir.mkdir(parents=True, exist_ok=True)
    return_part = request.return_date.isoformat() if request.return_date else "ow"
    name = (
        f"{collected_on.isoformat()}_{request.origin}-{request.dest}_"
        f"{request.outbound_date.isoformat()}_{return_part}_{request.trip_type}.json"
    )
    path = raw_dir / name
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def _sleep(settings: Settings) -> None:
    delay = settings.request_delay_seconds
    jitter = settings.request_jitter_seconds
    wait = delay + random.uniform(0, jitter) if jitter else delay
    if wait > 0:
        time.sleep(wait)


def _search_with_retry(adapter, request: SearchRequest, settings: Settings) -> SearchResult:
    last: SearchResult | None = None
    for attempt in range(1, settings.max_retries + 1):
        last = adapter.search(request)
        if last.status != "error":
            return last
        logger.warning(
            "Keresés hiba (%s/%s) %s %s %s: %s",
            attempt,
            settings.max_retries,
            request.origin,
            request.dest,
            request.outbound_date,
            last.error,
        )
        if attempt < settings.max_retries:
            time.sleep(min(30, 5 * attempt))
    assert last is not None
    return last


def collect(
    settings: Settings,
    *,
    source_name: str | None = None,
    limit: int | None = None,
    pinned_only: bool = False,
    only_date: date | None = None,
    force: bool = False,
    dry_run: bool = False,
    today: date | None = None,
) -> CollectSummary:
    source_name = source_name or settings.source
    adapter = get_adapter(source_name)
    today = today or today_in_tz(settings.timezone)
    jobs = build_jobs(
        settings,
        today,
        limit=limit,
        pinned_only=pinned_only,
        only_date=only_date,
    )
    summary = CollectSummary(planned=len(jobs))
    logger.info(
        "Gyűjtés: %s job, forrás=%s, collected_on=%s",
        len(jobs),
        adapter.name,
        today.isoformat(),
    )
    if dry_run:
        for job in jobs:
            logger.info(
                "dry-run %s %s-%s %s %s",
                job.trip_type,
                job.origin,
                job.dest,
                job.outbound_date,
                job.return_date or "-",
            )
        return summary

    started_at = datetime.now().astimezone()
    started_mono = time.perf_counter()
    conn = connect(settings.db_path)
    try:
        for index, request in enumerate(jobs):
            existing = existing_snapshot(
                conn, collected_on=today, request=request, source=adapter.name
            )
            replace_id = existing[0] if existing else None
            if existing is not None and existing[1] == "ok" and not force:
                summary.skipped += 1
                continue
            result = _search_with_retry(adapter, request, settings)
            raw_path = _write_raw(settings.raw_dir, today, request, result.raw)
            save_result(
                conn,
                collected_on=today,
                source=adapter.name,
                result=result,
                raw_path=raw_path,
                replace_id=replace_id,
            )
            if result.status == "ok":
                summary.ok += 1
            elif result.status == "empty":
                summary.empty += 1
            else:
                summary.error += 1
            logger.info(
                "[%s/%s] %s %s-%s %s → %s (%s ajánlat)",
                index + 1,
                len(jobs),
                request.trip_type,
                request.origin,
                request.dest,
                request.outbound_date,
                result.status,
                len(result.offers),
            )
            if index + 1 < len(jobs):
                _sleep(settings)
        finished_at = datetime.now().astimezone()
        summary.duration_seconds = time.perf_counter() - started_mono
        save_collect_run(
            conn,
            collected_on=today,
            source=adapter.name,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=summary.duration_seconds,
            planned=summary.planned,
            skipped=summary.skipped,
            ok=summary.ok,
            empty=summary.empty,
            error=summary.error,
        )
        logger.info(
            "Gyűjtés kész: %.1f perc (%s ok, %s hiba, %s üres, %s kihagyva)",
            summary.duration_seconds / 60,
            summary.ok,
            summary.error,
            summary.empty,
            summary.skipped,
        )
    finally:
        conn.close()
    return summary
