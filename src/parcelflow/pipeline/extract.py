"""Extract step: produce raw files in blob storage and read them back.

In a real system an upstream team would drop daily files into object storage.
Here the Olist source (``source/olist.py``) plays that role: ``extract_to_storage``
slices the real orders for one day and writes one CSV per destination state into
the ``raw/`` prefix, partitioned by date. ``read_partition`` reads every file
for a date back into a single DataFrame, exactly as the load step would consume
them from Azure Blob / Azurite.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from ..config import Settings, get_settings
from ..source.olist import write_partition
from ..storage.base import StorageBackend

# Keep string columns as strings so quality checks see raw values (e.g. a blank
# customer_state stays blank rather than becoming NaN of a numeric column).
_RAW_DTYPES = {
    "order_id": "string",
    "purchase_date": "string",
    "customer_state": "string",
    "order_status": "string",
    "delivered_date": "string",
    "estimated_date": "string",
}


def extract_to_storage(
    d: date, storage: StorageBackend, settings: Settings | None = None
) -> list[str]:
    """Write one day's real orders to storage, per state. Idempotent (overwrites)."""
    settings = settings or get_settings()
    return write_partition(d, storage, settings)


def read_partition(d: date, storage: StorageBackend) -> pd.DataFrame:
    """Read all raw CSV files for date ``d`` into one DataFrame."""
    prefix = f"raw/date={d.isoformat()}/"
    keys = storage.list_keys(prefix)
    frames: list[pd.DataFrame] = []
    for key in keys:
        raw = storage.read_bytes(key)
        frames.append(pd.read_csv(io.BytesIO(raw), dtype=_RAW_DTYPES))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
