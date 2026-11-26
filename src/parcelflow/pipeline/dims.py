"""Seed and maintain the conformed dimensions.

``dim_hub`` (states) and ``dim_order_status`` are static reference data.
``dim_date`` is grown as new dates appear. All three are seeded idempotently
(insert only the keys that are missing), so calling these functions repeatedly
is safe.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Engine, select

from ..db.schema import dim_date, dim_hub, dim_order_status
from ..source.states import ORDER_STATUSES, STATES

HOLIDAY_MONTHS = {11, 12}  # Black Friday / Christmas peak (real Olist spike)
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def seed_hub_and_status(engine: Engine) -> None:
    """Insert the static hub (state) and order-status dimensions if absent."""
    with engine.begin() as conn:
        existing_hubs = set(conn.execute(select(dim_hub.c.hub_code)).scalars())
        new_hubs = [
            {
                "hub_key": i + 1,
                "hub_code": s.code,
                "hub_name": s.name,
                "city": s.capital,
                "region": s.region,
                "lat": s.lat,
                "lng": s.lng,
            }
            for i, s in enumerate(STATES)
            if s.code not in existing_hubs
        ]
        if new_hubs:
            conn.execute(dim_hub.insert(), new_hubs)

        existing_status = set(
            conn.execute(select(dim_order_status.c.order_status)).scalars()
        )
        new_status = [
            {"status_key": i + 1, "order_status": s}
            for i, s in enumerate(ORDER_STATUSES)
            if s not in existing_status
        ]
        if new_status:
            conn.execute(dim_order_status.insert(), new_status)


def _date_row(d: date) -> dict:
    return {
        "date_key": int(d.strftime("%Y%m%d")),
        "date": d.isoformat(),
        "year": d.year,
        "quarter": (d.month - 1) // 3 + 1,
        "month": d.month,
        "day": d.day,
        "day_of_week": d.weekday(),
        "day_name": DAY_NAMES[d.weekday()],
        "week_of_year": int(d.strftime("%W")),
        "is_weekend": d.weekday() >= 5,
        "is_holiday_season": d.month in HOLIDAY_MONTHS,
    }


def seed_dates(engine: Engine, dates: list[date]) -> None:
    """Insert any of ``dates`` not already in ``dim_date``."""
    if not dates:
        return
    keys = [int(d.strftime("%Y%m%d")) for d in dates]
    with engine.begin() as conn:
        existing = set(
            conn.execute(
                select(dim_date.c.date_key).where(dim_date.c.date_key.in_(keys))
            ).scalars()
        )
        rows = [_date_row(d) for d in dates if int(d.strftime("%Y%m%d")) not in existing]
        if rows:
            conn.execute(dim_date.insert(), rows)


def seed_dates_from_iso(engine: Engine, iso_dates: list[str]) -> None:
    """Convenience wrapper: seed dim_date from ISO date strings."""
    dates = [datetime.strptime(s, "%Y-%m-%d").date() for s in sorted(set(iso_dates))]
    seed_dates(engine, dates)
