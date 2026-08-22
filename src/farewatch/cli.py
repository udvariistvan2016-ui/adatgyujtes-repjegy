from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

from farewatch.analysis import run_analysis
from farewatch.collector import collect
from farewatch.config import load_settings
from farewatch.dashboard import write_dashboard
from farewatch.db import connect, status_rows


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_collect(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    only_date = date.fromisoformat(args.date) if args.date else None
    summary = collect(
        settings,
        source_name=args.source,
        limit=args.limit,
        pinned_only=args.pinned_only,
        only_date=only_date,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(
        f"planned={summary.planned} skipped={summary.skipped} "
        f"ok={summary.ok} empty={summary.empty} error={summary.error} "
        f"duration_min={summary.duration_seconds / 60:.1f}"
    )
    if not args.dry_run and not args.no_dashboard:
        dash = write_dashboard(settings)
        print(f"dashboard={dash}")
    if summary.error:
        print("Volt sikertelen keresés. Ugyanezen a napon újra futtatható: a hibásak automatikusan újrapróbálódnak.")
    return 1 if summary.error and not summary.ok else 0


def _cmd_status(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if not settings.db_path.exists():
        print(f"Nincs adatbázis még: {settings.db_path}")
        return 0
    conn = connect(settings.db_path)
    try:
        info = status_rows(conn)
    finally:
        conn.close()
    print(f"snapshots={info['snapshots']} offers={info['offers']}")
    print(f"latest_collected_on={info['latest_collected_on']}")
    print(f"by_status={info['by_status']}")
    print("pinned RT 2027-03-12 / 03-15 (utolsó napok):")
    if not info["pinned_recent"]:
        print("  (még nincs adat)")
    for row in info["pinned_recent"]:
        price = row["min_price"]
        price_s = f"{price:.0f} {row['currency'] or ''}".strip() if price is not None else "-"
        print(
            f"  {row['collected_on']}  status={row['status']}  "
            f"offers={row['offer_count']}  min={price_s}"
        )
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if not settings.db_path.exists():
        print(f"Nincs adatbázis még: {settings.db_path}")
        return 1
    result = run_analysis(settings)
    print(f"horizon CSV: {result['horizon_csv']} ({result['horizon_rows']} sor)")
    print(f"pinned CSV:  {result['pinned_csv']} ({result['pinned_rows']} sor)")
    if result["horizon_plot"]:
        print(f"horizon ábra: {result['horizon_png']}")
    if result["pinned_plot"]:
        print(f"pinned ábra:  {result['pinned_png']}")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    path = write_dashboard(settings)
    print(f"dashboard={path}")
    return 0


def _cmd_backup(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if not settings.db_path.exists():
        print(f"Nincs adatbázis: {settings.db_path}")
        return 1
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    dest = settings.backups_dir / f"fares-{stamp}.sqlite3"
    shutil.copy2(settings.db_path, dest)
    keep = args.keep
    backups = sorted(settings.backups_dir.glob("fares-*.sqlite3"), reverse=True)
    for old in backups[keep:]:
        old.unlink()
    print(f"backup: {dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="farewatch", description="BUD–MAD jegyár-gyűjtő")
    parser.add_argument("--config", type=Path, default=None, help="config.yaml útvonal")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    collect_p = sub.add_parser("collect", help="Napi gyűjtés")
    collect_p.add_argument("--source", choices=["google_flights", "mock"])
    collect_p.add_argument("--limit", type=int, default=None, help="Csak ennyi horizont-dátum")
    collect_p.add_argument("--date", help="Egy konkrét OW dátum (YYYY-MM-DD)")
    collect_p.add_argument("--pinned-only", action="store_true")
    collect_p.add_argument("--force", action="store_true", help="Mai snapshot felülírása")
    collect_p.add_argument("--dry-run", action="store_true")
    collect_p.add_argument("--no-dashboard", action="store_true")
    collect_p.set_defaults(func=_cmd_collect)

    status_p = sub.add_parser("status", help="Adatbázis összefoglaló")
    status_p.set_defaults(func=_cmd_status)

    analyze_p = sub.add_parser("analyze", help="CSV és ábrák")
    analyze_p.set_defaults(func=_cmd_analyze)

    dash_p = sub.add_parser("dashboard", help="Statikus HTML a docs/ mappába")
    dash_p.set_defaults(func=_cmd_dashboard)

    backup_p = sub.add_parser("backup", help="SQLite másolat data/backups alá")
    backup_p.add_argument("--keep", type=int, default=14)
    backup_p.set_defaults(func=_cmd_backup)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
