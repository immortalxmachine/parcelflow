"""Real-data source: the Olist Brazilian e-commerce dataset.

This module replaces the old synthetic generator. Instead of fabricating rows,
it reads the **real** Olist CSV files (`olistbr/brazilian-ecommerce` on Kaggle,
CC-BY-NC-SA 4.0) and shapes them into the daily, per-state partitions the ELT
pipeline consumes.

One *order* becomes one row (one parcel shipped to a customer). Orders are
grouped to the destination **customer state** (the "hub") and the **purchase
date**, so the pipeline's `raw/date=YYYY-MM-DD/<STATE>.csv` partitions are just
the real orders placed that day for that state.

What is read:
  * ``olist_orders_dataset.csv``     - status + purchase / delivered / estimated
  * ``olist_customers_dataset.csv``  - customer_state (the hub)
  * ``olist_order_items_dataset.csv`` - per-order price, freight, item count

Everything written downstream is derived directly from these files; no value is
invented. Orders are restricted to the dense, complete ordering window (see
``WINDOW_START`` / ``WINDOW_END``) - the 2016 pilot months and the truncated
final weeks of 2018 are excluded so the daily series is a regular grid.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

import pandas as pd

from ..config import Settings, get_settings
from ..storage.base import StorageBackend
from .states import STATE_CODES

# Dense, complete ordering window. Outside this range Olist has only a handful
# of pilot orders (late 2016) and a truncated tail (Sept-Oct 2018) that would
# leave large gaps in a daily series.
WINDOW_START = date(2017, 1, 1)
# Order collection tapers off after 2018-08-22 (a cliff from ~190 to <150/day
# and collapsing to single digits by month-end), so the last complete day is
# 2018-08-22. Including the tail would put the forecast holdout in incomplete
# data and wreck the back-test.
WINDOW_END = date(2018, 8, 22)

# Columns written to each raw partition CSV (one row per order).
COLUMNS = [
    "order_id",
    "purchase_date",     # YYYY-MM-DD (order_purchase_timestamp, date part)
    "customer_state",    # hub
    "order_status",
    "price",             # sum of order-item prices (blank if no items)
    "freight_value",     # sum of order-item freight (blank if no items)
    "n_items",           # number of order items
    "delivery_days",     # days purchase -> delivered to customer (blank if n/a)
    "delivered_date",    # YYYY-MM-DD (blank if not delivered)
    "estimated_date",    # YYYY-MM-DD estimated delivery date
]


def _iso_date(ts: pd.Timestamp) -> str:
    return "" if pd.isna(ts) else ts.date().isoformat()


@lru_cache(maxsize=2)
def _load_source(olist_dir: str) -> pd.DataFrame:
    """Read + join the Olist CSVs into one order-level frame (cached per dir).

    The result has one row per order within the window, with the destination
    state, order status, item aggregates and delivery timings. All values come
    straight from the source files.
    """
    root = olist_dir.rstrip("/\\")
    orders = pd.read_csv(f"{root}/olist_orders_dataset.csv")
    customers = pd.read_csv(
        f"{root}/olist_customers_dataset.csv",
        usecols=["customer_id", "customer_state"],
    )
    items = pd.read_csv(
        f"{root}/olist_order_items_dataset.csv",
        usecols=["order_id", "order_item_id", "price", "freight_value"],
    )

    # Parse the real timestamps.
    purchase = pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
    delivered = pd.to_datetime(orders["order_delivered_customer_date"], errors="coerce")
    estimated = pd.to_datetime(orders["order_estimated_delivery_date"], errors="coerce")

    df = pd.DataFrame(
        {
            "order_id": orders["order_id"],
            "customer_id": orders["customer_id"],
            "order_status": orders["order_status"],
            "_purchase": purchase,
            "_delivered": delivered,
            "_estimated": estimated,
        }
    )

    # Destination state (the hub).
    df = df.merge(customers, on="customer_id", how="left")

    # Per-order item aggregates (real sums; orders with no items get NaN/0).
    agg = items.groupby("order_id").agg(
        price=("price", "sum"),
        freight_value=("freight_value", "sum"),
        n_items=("order_item_id", "size"),
    )
    df = df.merge(agg, on="order_id", how="left")
    df["n_items"] = df["n_items"].fillna(0).astype(int)

    # Restrict to the dense window by purchase date.
    df = df[df["_purchase"].notna()]
    pdate = df["_purchase"].dt.date
    df = df[(pdate >= WINDOW_START) & (pdate <= WINDOW_END)].copy()

    # Real delivery duration (whole days), only where a delivery happened.
    delta = (df["_delivered"] - df["_purchase"]).dt.days
    df["delivery_days"] = delta

    df["purchase_date"] = df["_purchase"].dt.date.map(lambda d: d.isoformat())
    df["delivered_date"] = df["_delivered"].map(_iso_date)
    df["estimated_date"] = df["_estimated"].map(_iso_date)
    return df.reset_index(drop=True)


def load_orders(settings: Settings | None = None) -> pd.DataFrame:
    """Return the order-level source frame for the configured Olist directory."""
    settings = settings or get_settings()
    return _load_source(settings.olist_dir)


def available_dates(settings: Settings | None = None) -> list[date]:
    """Sorted list of purchase dates present in the (windowed) source."""
    df = load_orders(settings)
    return sorted({datetime.strptime(s, "%Y-%m-%d").date() for s in df["purchase_date"]})


def available_window(settings: Settings | None = None) -> tuple[date, date]:
    """(first, last) purchase date present in the source (within the window)."""
    dates = available_dates(settings)
    return dates[0], dates[-1]


def raw_key(d: date, state_code: str) -> str:
    """Blob key for one state's orders on one day, partitioned by date."""
    return f"raw/date={d.isoformat()}/{state_code}.csv"


def _rows_to_csv(frame: pd.DataFrame) -> bytes:
    return frame[COLUMNS].to_csv(index=False).encode("utf-8")


def write_partition(
    d: date, storage: StorageBackend, settings: Settings | None = None
) -> list[str]:
    """Write one day's real orders to storage, one CSV per destination state.

    Only states that actually received an order that day get a file (no empty
    partitions). Returns the blob keys written. Idempotent: overwrites.
    """
    settings = settings or get_settings()
    df = load_orders(settings)
    iso = d.isoformat()
    day = df[df["purchase_date"] == iso]

    keys: list[str] = []
    for state_code, chunk in day.groupby("customer_state"):
        if state_code not in STATE_CODES:
            # Unknown state codes are left for the quality stage to catch; the
            # partition still carries them so nothing is silently dropped.
            pass
        key = raw_key(d, str(state_code))
        storage.write_bytes(key, _rows_to_csv(chunk))
        keys.append(key)
    return keys
