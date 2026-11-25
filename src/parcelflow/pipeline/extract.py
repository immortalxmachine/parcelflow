"""Extract step: produce raw files in blob storage and read them back.

In a real system an upstream team would drop daily files into object storage.
Here the generator plays that role: ``extract_to_storage`` writes one CSV per
hub per day into the ``raw/`` prefix, partitioned by date. ``read_partition``
reads every file for a date back into a single DataFrame, exactly as the load
step would consume them from Azure Blob / Azurite.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from ..config import Settings, get_settings
from ..generate.generator import generate_and_store
from ..storage.base import StorageBackend

# Keep string columns as strings so quality checks see raw values (e.g. a blank
# hub_code stays blank rather than becoming NaN of a numeric column).
_RAW_DTYPES = {
    "shipment_id": "string",
    "ship_date": "string",
    "hub_code": "string",
    "service_type": "string",
    "status": "string",
}


def extract_to_storage(
    d: date, storage: StorageBackend, settings: Settings | None = None
) -> list[str]:
    """Generate and upload one day's raw files. Idempotent (overwrites)."""
    settings = settings or get_settings()
    return generate_and_store(d, storage, volume_scale=settings.volume_scale)


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
