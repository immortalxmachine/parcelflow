"""Load step: clean rows -> staging, bad rows -> quarantine.

Both loads are **idempotent**: before inserting a partition they delete any
rows already present for that ``load_date``. Re-running ``pipeline run`` for a
date therefore yields the same tables rather than duplicating data.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, text

from ..db.schema import quarantine_shipments, stg_shipments

_STG_COLS = [
    "shipment_id", "ship_date", "hub_code", "service_type", "weight_kg",
    "distance_km", "promised_hours", "actual_hours", "status", "load_date",
]
_QUAR_COLS = _STG_COLS[:-1] + ["reason", "load_date"]


def _delete_partition(engine: Engine, table_name: str, load_date: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {table_name} WHERE load_date = :d"),
            {"d": load_date},
        )


def load_staging(engine: Engine, clean: pd.DataFrame, load_date: str) -> int:
    """Replace staging rows for ``load_date`` with ``clean``. Returns row count."""
    _delete_partition(engine, stg_shipments.name, load_date)
    if clean.empty:
        return 0
    df = clean.copy()
    df["load_date"] = load_date
    df = df[_STG_COLS]
    df.to_sql(stg_shipments.name, engine, if_exists="append", index=False)
    return len(df)


def load_quarantine(engine: Engine, quarantine: pd.DataFrame, load_date: str) -> int:
    """Replace quarantine rows for ``load_date``. Returns row count."""
    _delete_partition(engine, quarantine_shipments.name, load_date)
    if quarantine.empty:
        return 0
    df = quarantine.copy()
    df["load_date"] = load_date
    # Numeric columns are stored as text in quarantine so raw invalid values
    # (e.g. a negative weight) survive for auditing.
    for col in ["weight_kg", "distance_km", "promised_hours", "actual_hours"]:
        df[col] = df[col].astype("string")
    df = df[_QUAR_COLS]
    df.to_sql(quarantine_shipments.name, engine, if_exists="append", index=False)
    return len(df)
