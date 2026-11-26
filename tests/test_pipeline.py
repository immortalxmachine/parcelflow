"""End-to-end pipeline tests on a throwaway SQLite warehouse."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from parcelflow.db.sqlfile import get_query
from parcelflow.pipeline import runner
from parcelflow.source.states import ORDER_STATUSES, STATES

# A dense day in the Olist window (Black Friday 2017).
DAY = date(2017, 11, 24)


def test_run_for_date_populates_warehouse(engine, storage, settings):
    result = runner.run_for_date(DAY, engine=engine, storage=storage, settings=settings)
    assert result.status == "SUCCESS"
    assert result.rows_in > 0
    # Cleaned rows should equal the fact rows loaded (grain = one order).
    assert result.rows_passed == result.fact_rows
    assert result.rows_in == result.rows_passed + result.rows_quarantined


def test_run_is_idempotent(engine, storage, settings):
    r1 = runner.run_for_date(DAY, engine=engine, storage=storage, settings=settings)
    r2 = runner.run_for_date(DAY, engine=engine, storage=storage, settings=settings)
    # Re-running must not duplicate rows.
    assert r1.fact_rows == r2.fact_rows
    with engine.connect() as conn:
        facts = conn.execute(text("SELECT COUNT(*) FROM fact_shipments")).scalar_one()
    assert facts == r1.fact_rows


def test_dimensions_seeded(engine, storage, settings):
    runner.run_for_date(DAY, engine=engine, storage=storage, settings=settings)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM dim_hub")).scalar_one() == len(STATES)
        assert (
            conn.execute(text("SELECT COUNT(*) FROM dim_order_status")).scalar_one()
            == len(ORDER_STATUSES)
        )
        assert conn.execute(text("SELECT COUNT(*) FROM dim_date")).scalar_one() == 1


def test_kpi_queries_run(engine, storage, settings):
    runner.run_for_date(DAY, engine=engine, storage=storage, settings=settings)
    with engine.connect() as conn:
        for name in [
            "daily_volume_by_hub", "volume_7day_moving_avg", "on_time_rate_by_hub",
            "hub_utilisation_rank", "monthly_volume_trend", "daily_total_volume",
            "hub_volume_stats",
        ]:
            rows = conn.execute(text(get_query("kpis.sql", name))).fetchall()
            assert rows, f"{name} returned no rows"


def test_on_time_is_computed(engine, storage, settings):
    runner.run_for_date(DAY, engine=engine, storage=storage, settings=settings)
    with engine.connect() as conn:
        delivered, on_time = conn.execute(
            text(
                "SELECT SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END) FROM fact_shipments"
            )
        ).fetchone()
    # A dense real day has delivered orders, most of them on time.
    assert delivered > 0
    assert 0 < on_time <= delivered
