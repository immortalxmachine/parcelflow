"""Pipeline orchestration for a single date (idempotent, safe to re-run).

One ``run_date`` flows through the medallion-style stages:

    extract  -> raw CSV files land in blob storage (raw/date=.../hub.csv)
    load     -> raw rows read into the staging table
    quality  -> rows screened; clean -> staging kept, bad -> quarantine
    transform-> clean rows loaded into the star-schema fact table
    run_log  -> one row recording rows in / passed / quarantined

Every stage deletes-then-writes its partition, so re-running a date converges
to the same result instead of duplicating rows.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone

from sqlalchemy import Engine, text

from ..config import Settings, get_settings
from ..db.engine import get_engine
from ..db.schema import create_all, run_log
from ..storage import get_storage
from ..storage.base import StorageBackend
from . import dims, extract, load, quality, transform


@dataclass
class RunResult:
    run_id: str
    run_date: str
    rows_in: int
    rows_passed: int
    rows_quarantined: int
    fact_rows: int
    status: str


def run_for_date(
    run_date: date,
    *,
    engine: Engine | None = None,
    storage: StorageBackend | None = None,
    settings: Settings | None = None,
    generate: bool = True,
) -> RunResult:
    """Run the full pipeline for ``run_date`` and return a summary.

    If ``generate`` is True, raw files are (re)generated into storage first;
    set it False to run against raw files already present in storage.
    """
    settings = settings or get_settings()
    engine = engine or get_engine(settings.database_url)
    storage = storage or get_storage(settings)

    create_all(engine)
    dims.seed_hub_and_service(engine)

    iso = run_date.isoformat()
    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1. Extract: ensure raw files exist in blob storage for this date.
    if generate:
        extract.extract_to_storage(run_date, storage, settings)
    raw = extract.read_partition(run_date, storage)
    rows_in = len(raw)

    # 2. Quality screen.
    clean, quarantine = quality.screen(raw)

    # 3. Seed the date dimension before loading facts that reference it.
    dims.seed_dates(engine, [run_date])

    # 4. Load staging + quarantine.
    rows_passed = load.load_staging(engine, clean, iso)
    rows_quarantined = load.load_quarantine(engine, quarantine, iso)

    # 5. Transform into the fact table.
    fact_rows = transform.build_fact_for_partition(engine, iso)

    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = RunResult(
        run_id=run_id,
        run_date=iso,
        rows_in=rows_in,
        rows_passed=rows_passed,
        rows_quarantined=rows_quarantined,
        fact_rows=fact_rows,
        status="SUCCESS",
    )
    _write_run_log(engine, result, started, finished)
    return result


def _write_run_log(engine: Engine, result: RunResult, started: str, finished: str) -> None:
    with engine.begin() as conn:
        # Idempotent: one log row per run_date (latest run wins).
        conn.execute(text("DELETE FROM run_log WHERE run_date = :d"), {"d": result.run_date})
        conn.execute(
            run_log.insert(),
            {
                "run_id": result.run_id,
                "run_date": result.run_date,
                "started_at": started,
                "finished_at": finished,
                "rows_in": result.rows_in,
                "rows_passed": result.rows_passed,
                "rows_quarantined": result.rows_quarantined,
                "status": result.status,
            },
        )


def run_backfill(
    start: date,
    end: date,
    *,
    engine: Engine | None = None,
    storage: StorageBackend | None = None,
    settings: Settings | None = None,
    progress_every: int = 30,
) -> list[RunResult]:
    """Run the pipeline for every date in [start, end]. Returns per-day results."""
    settings = settings or get_settings()
    engine = engine or get_engine(settings.database_url)
    storage = storage or get_storage(settings)

    results: list[RunResult] = []
    cur = start
    i = 0
    while cur <= end:
        results.append(
            run_for_date(cur, engine=engine, storage=storage, settings=settings)
        )
        i += 1
        if progress_every and i % progress_every == 0:
            print(f"  ...processed {i} days (through {cur.isoformat()})")
        cur = cur.toordinal()
        cur = date.fromordinal(cur + 1)
    return results


def summarise(results: list[RunResult]) -> dict:
    """Aggregate a list of run results into totals (for CLI output)."""
    return {
        "days": len(results),
        "rows_in": sum(r.rows_in for r in results),
        "rows_passed": sum(r.rows_passed for r in results),
        "rows_quarantined": sum(r.rows_quarantined for r in results),
        "fact_rows": sum(r.fact_rows for r in results),
    }


def result_as_dict(result: RunResult) -> dict:
    return asdict(result)
