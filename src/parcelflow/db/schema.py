"""Database schema (staging, quarantine, run log + star-schema warehouse).

Defined with SQLAlchemy Core so the same definitions emit valid DDL on both
SQLite (local/CI) and PostgreSQL (Docker/cloud). The warehouse uses a classic
**star schema**: a central ``fact_shipments`` table referencing conformed
dimensions ``dim_hub`` (Brazilian customer state), ``dim_date`` and
``dim_order_status``.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

# --------------------------------------------------------------------------- #
# Landing / operational tables
# --------------------------------------------------------------------------- #

# Raw rows loaded from blob storage, before quality screening. One row per
# order (= one parcel shipped to a customer), sourced from the Olist dataset.
stg_shipments = Table(
    "stg_shipments",
    metadata,
    Column("order_id", String(40)),
    Column("purchase_date", String(10)),
    Column("customer_state", String(4)),   # the hub
    Column("order_status", String(16)),
    Column("price", Float),
    Column("freight_value", Float),
    Column("n_items", Integer),
    Column("delivery_days", Float),
    Column("delivered_date", String(10)),
    Column("estimated_date", String(10)),
    Column("load_date", String(10), index=True),  # partition this batch belongs to
)

# Rows that failed a data-quality rule, kept with the reason for auditing.
quarantine_shipments = Table(
    "quarantine_shipments",
    metadata,
    Column("order_id", String(40)),
    Column("purchase_date", String(10)),
    Column("customer_state", String(4)),
    Column("order_status", String(16)),
    Column("price", String(32)),           # text: may hold the raw invalid value
    Column("freight_value", String(32)),
    Column("n_items", String(32)),
    Column("delivery_days", String(32)),
    Column("delivered_date", String(10)),
    Column("estimated_date", String(10)),
    Column("reason", Text),
    Column("load_date", String(10), index=True),
)

# One row per pipeline execution, for observability.
run_log = Table(
    "run_log",
    metadata,
    Column("run_id", String(40), primary_key=True),
    Column("run_date", String(10), index=True),
    Column("started_at", String(32)),
    Column("finished_at", String(32)),
    Column("rows_in", Integer),
    Column("rows_passed", Integer),
    Column("rows_quarantined", Integer),
    Column("status", String(16)),
)

# --------------------------------------------------------------------------- #
# Warehouse - star schema
# --------------------------------------------------------------------------- #

dim_hub = Table(
    "dim_hub",
    metadata,
    Column("hub_key", Integer, primary_key=True),  # surrogate key
    Column("hub_code", String(8), unique=True),
    Column("hub_name", String(64)),
    Column("city", String(64)),
    Column("region", String(16)),
    Column("lat", Float),
    Column("lng", Float),
)

dim_order_status = Table(
    "dim_order_status",
    metadata,
    Column("status_key", Integer, primary_key=True),
    Column("order_status", String(16), unique=True),
)

dim_date = Table(
    "dim_date",
    metadata,
    Column("date_key", Integer, primary_key=True),  # yyyymmdd
    Column("date", String(10), unique=True),
    Column("year", Integer),
    Column("quarter", Integer),
    Column("month", Integer),
    Column("day", Integer),
    Column("day_of_week", Integer),   # 0=Mon .. 6=Sun
    Column("day_name", String(10)),
    Column("week_of_year", Integer),
    Column("is_weekend", Boolean),
    Column("is_holiday_season", Boolean),  # Nov-Dec (Black Friday / Christmas)
)

fact_shipments = Table(
    "fact_shipments",
    metadata,
    # Integer PK aliases SQLite's rowid (auto-increments on INSERT...SELECT)
    # and becomes SERIAL on PostgreSQL.
    Column("fact_id", Integer, primary_key=True, autoincrement=True),
    Column("date_key", Integer, ForeignKey("dim_date.date_key"), index=True),
    Column("hub_key", Integer, ForeignKey("dim_hub.hub_key"), index=True),
    Column("status_key", Integer, ForeignKey("dim_order_status.status_key"), index=True),
    Column("price", Float),
    Column("freight_value", Float),
    Column("n_items", Integer),
    Column("delivery_days", Float),
    Column("is_delivered", Boolean),
    Column("is_on_time", Boolean),
)


def create_all(engine) -> None:
    """Create every table if it does not already exist."""
    metadata.create_all(engine)


def drop_all(engine) -> None:
    """Drop every table (used by tests and ``initdb --reset``)."""
    metadata.drop_all(engine)
