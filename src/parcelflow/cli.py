"""ParcelFlow command-line interface.

Subcommands:
    initdb                     create (or reset) all tables + seed dimensions
    run      --date YYYY-MM-DD run the pipeline for one day (idempotent)
    backfill --start .. --end  run the pipeline for a date range
    forecast                   back-test SARIMA vs baseline; write metrics.json
    status                     print row counts and the latest run log

Example:
    python pipeline.py backfill                 # full Olist window
    python pipeline.py run --date 2017-11-24    # one day (Black Friday)
    python pipeline.py forecast
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime

from sqlalchemy import text

from .config import PROJECT_ROOT, get_settings
from .db.engine import get_engine
from .db.schema import create_all, drop_all
from .forecast.forecast import evaluate_all, forecastable_hubs
from .pipeline import dims, runner
from .source import olist

METRICS_PATH = PROJECT_ROOT / "metrics.json"


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_initdb(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    if args.reset:
        drop_all(engine)
        print("Dropped all tables.")
    create_all(engine)
    dims.seed_hub_and_status(engine)
    print(f"Initialised schema at {settings.database_url}")


def cmd_run(args: argparse.Namespace) -> None:
    run_date = _parse_date(args.date)
    result = runner.run_for_date(run_date)
    print(json.dumps(runner.result_as_dict(result), indent=2))


def cmd_backfill(args: argparse.Namespace) -> None:
    # Default to the full window actually present in the Olist source data.
    src_start, src_end = olist.available_window()
    start = _parse_date(args.start) if args.start else src_start
    end = _parse_date(args.end) if args.end else src_end
    print(f"Backfilling {start} .. {end} ({(end - start).days + 1} days)")
    results = runner.run_backfill(start, end)
    print(json.dumps(runner.summarise(results), indent=2))


def cmd_forecast(args: argparse.Namespace) -> None:
    engine = get_engine()
    codes = forecastable_hubs(engine, min_avg_per_day=args.min_per_day)
    if not codes:
        print("No hubs dense enough to forecast. Run a backfill first.")
        return
    print(f"Forecasting {len(codes)} dense states: {', '.join(codes)}")
    metrics = evaluate_all(engine, codes, holdout=args.holdout)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(
        {k: v for k, v in metrics.items() if k != "per_hub"}, indent=2
    ))
    print(f"\nWrote per-hub metrics to {METRICS_PATH}")


def cmd_status(args: argparse.Namespace) -> None:
    engine = get_engine()
    create_all(engine)
    with engine.connect() as conn:
        for table in [
            "stg_shipments", "quarantine_shipments", "fact_shipments",
            "dim_hub", "dim_order_status", "dim_date", "run_log",
        ]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            print(f"  {table:22s} {n:>10,}")
        last = conn.execute(
            text(
                "SELECT run_date, rows_in, rows_passed, rows_quarantined, status "
                "FROM run_log ORDER BY run_date DESC LIMIT 5"
            )
        ).fetchall()
    print("\nLatest runs:")
    for r in last:
        print(f"  {r[0]}  in={r[1]:>6}  passed={r[2]:>6}  quarantined={r[3]:>4}  {r[4]}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipeline.py", description="ParcelFlow ELT + forecasting")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("initdb", help="create/reset schema and seed dimensions")
    sp.add_argument("--reset", action="store_true", help="drop all tables first")
    sp.set_defaults(func=cmd_initdb)

    sp = sub.add_parser("run", help="run the pipeline for one date")
    sp.add_argument("--date", required=True, help="YYYY-MM-DD")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("backfill", help="run the pipeline for a date range")
    sp.add_argument("--start", help="YYYY-MM-DD (default: first date in source)")
    sp.add_argument("--end", help="YYYY-MM-DD (default: last date in source)")
    sp.set_defaults(func=cmd_backfill)

    sp = sub.add_parser("forecast", help="back-test forecasts; write metrics.json")
    sp.add_argument("--holdout", type=int, default=14, help="holdout days")
    sp.add_argument("--min-per-day", type=float, default=8.0,
                    help="min avg orders/day for a state to be forecast")
    sp.set_defaults(func=cmd_forecast)

    sp = sub.add_parser("status", help="print table counts and recent runs")
    sp.set_defaults(func=cmd_status)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
