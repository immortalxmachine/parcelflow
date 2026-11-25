"""End-to-end pipeline tests on a throwaway SQLite warehouse."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from parcelflow.db.sqlfile import get_query
from parcelflow.pipeline import runner


def test_run_for_date_populates_warehouse(engine, storage, settings):
    result = runner.run_for_date(
        date(2024, 10, 20), engine=engine, storage=storage, settings=settings
    )
    assert result.status == "SUCCESS"
    assert result.rows_in > 0
    # Cleaned rows should equal the fact rows loaded (grain = one shipment).
    assert result.rows_passed == result.fact_rows
    assert result.rows_in == result.rows_passed + result.rows_quarantined


def test_run_is_idempotent(engine, storage, settings):
    d = date(2024, 10, 20)
    r1 = runner.run_for_date(d, engine=engine, storage=storage, settings=settings)
    r2 = runner.run_for_date(d, engine=engine, storage=storage, settings=settings)
    # Re-running must not duplicate rows.
    assert r1.fact_rows == r2.fact_rows
    with engine.connect() as conn:
        facts = conn.execute(text("SELECT COUNT(*) FROM fact_shipments")).scalar_one()
    assert facts == r1.fact_rows


def test_dimensions_seeded(engine, storage, settings):
    runner.run_for_date(date(2024, 10, 20), engine=engine, storage=storage, settings=settings)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM dim_hub")).scalar_one() == 15
        assert conn.execute(text("SELECT COUNT(*) FROM dim_service")).scalar_one() == 3
        assert conn.execute(text("SELECT COUNT(*) FROM dim_date")).scalar_one() == 1


def test_kpi_queries_run(engine, storage, settings):
    runner.run_for_date(date(2024, 10, 20), engine=engine, storage=storage, settings=settings)
    with engine.connect() as conn:
        for name in [
            "daily_volume_by_hub", "volume_7day_moving_avg", "on_time_rate_by_hub",
            "hub_utilisation_rank", "monthly_volume_trend", "daily_total_volume",
        ]:
            rows = conn.execute(text(get_query("kpis.sql", name))).fetchall()
            assert rows, f"{name} returned no rows"


def test_quarantine_has_reasons(engine, storage, settings):
    runner.run_for_date(date(2024, 10, 20), engine=engine, storage=storage, settings=settings)
    with engine.connect() as conn:
        bad = conn.execute(
            text("SELECT reason FROM quarantine_shipments WHERE reason IS NOT NULL")
        ).fetchall()
    # Generator injects dirty rows, so there should be some quarantined rows.
    assert len(bad) > 0
