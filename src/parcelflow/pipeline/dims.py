"""Seed and maintain the conformed dimensions.

``dim_hub`` and ``dim_service`` are static reference data. ``dim_date`` is
grown as new dates appear. All three are seeded idempotently (insert only the
keys that are missing), so calling these functions repeatedly is safe.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Engine, select

from ..generate.hubs import HUBS, SERVICE_TYPES
from ..db.schema import dim_date, dim_hub, dim_service

MONSOON_MONTHS = {6, 7, 8, 9}
FESTIVAL_MONTHS = {10, 11}  # Diwali season (approx.)
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def seed_hub_and_service(engine: Engine) -> None:
    """Insert the static hub and service dimensions if absent."""
    with engine.begin() as conn:
        existing_hubs = set(conn.execute(select(dim_hub.c.hub_code)).scalars())
        new_hubs = [
            {
                "hub_key": i + 1,
                "hub_code": h.code,
                "hub_name": h.name,
                "city": h.city,
                "region": h.region,
                "lat": h.lat,
                "lng": h.lng,
            }
            for i, h in enumerate(HUBS)
            if h.code not in existing_hubs
        ]
        if new_hubs:
            conn.execute(dim_hub.insert(), new_hubs)

        existing_svc = set(conn.execute(select(dim_service.c.service_type)).scalars())
        new_svc = [
            {"service_key": i + 1, "service_type": s}
            for i, s in enumerate(SERVICE_TYPES)
            if s not in existing_svc
        ]
        if new_svc:
            conn.execute(dim_service.insert(), new_svc)


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
        "is_monsoon": d.month in MONSOON_MONTHS,
        "is_festival_season": d.month in FESTIVAL_MONTHS,
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
