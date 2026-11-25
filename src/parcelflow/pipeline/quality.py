"""Data-quality screening.

Splits a batch of raw rows into:

* **clean**      - rows that pass every rule, ready for the warehouse.
* **quarantine** - rows that fail a rule, tagged with the reason so they can
                   be audited and fixed rather than silently dropped.

Rules enforced (first failing rule wins as the reason):
    1. required fields present (not null/blank)
    2. ship_date is a real calendar date
    3. hub_code / service_type are known reference values
    4. numeric ranges (weight, distance, promised hours positive & sane)
    5. duplicate shipment_id (keep first occurrence, quarantine the rest)
"""

from __future__ import annotations

import pandas as pd

from ..generate.hubs import HUBS_BY_CODE, SERVICE_TYPES

REQUIRED_FIELDS = ["shipment_id", "ship_date", "hub_code", "service_type", "status"]
MAX_WEIGHT_KG = 100.0
MAX_DISTANCE_KM = 5000.0
VALID_HUB_CODES = set(HUBS_BY_CODE)
VALID_SERVICE_TYPES = set(SERVICE_TYPES)


def _blank(series: pd.Series) -> pd.Series:
    """True where a value is null or an empty/whitespace string."""
    return series.isna() | (series.astype(str).str.strip() == "")


def screen(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(clean_df, quarantine_df)``.

    ``quarantine_df`` carries an extra ``reason`` column. The input is not
    mutated. An empty input yields two empty frames.
    """
    if df.empty:
        return df.copy(), df.assign(reason=pd.Series(dtype="object"))

    df = df.copy()
    # Reason accumulator: first non-empty reason per row is what we keep.
    reason = pd.Series([""] * len(df), index=df.index, dtype="object")

    def flag(mask: pd.Series, text: str) -> None:
        # Only set a reason where none has been recorded yet.
        target = mask & (reason == "")
        reason.loc[target] = text

    # 1. Required fields present.
    for field in REQUIRED_FIELDS:
        flag(_blank(df[field]), f"null_{field}")

    # 2. ship_date must be a real date (YYYY-MM-DD).
    parsed = pd.to_datetime(df["ship_date"], format="%Y-%m-%d", errors="coerce")
    flag(parsed.isna(), "bad_ship_date")

    # 3. Reference-data validity.
    flag(~df["hub_code"].isin(VALID_HUB_CODES), "unknown_hub_code")
    flag(~df["service_type"].isin(VALID_SERVICE_TYPES), "unknown_service_type")

    # 4. Numeric ranges. Coerce first so non-numeric text is caught too.
    weight = pd.to_numeric(df["weight_kg"], errors="coerce")
    distance = pd.to_numeric(df["distance_km"], errors="coerce")
    promised = pd.to_numeric(df["promised_hours"], errors="coerce")
    flag(weight.isna() | (weight <= 0) | (weight > MAX_WEIGHT_KG), "bad_weight_kg")
    flag(distance.isna() | (distance <= 0) | (distance > MAX_DISTANCE_KM), "bad_distance_km")
    flag(promised.isna() | (promised <= 0), "bad_promised_hours")

    # 5. Duplicate shipment_id - keep the first, quarantine later copies.
    dup = df.duplicated(subset=["shipment_id"], keep="first")
    flag(dup, "duplicate_shipment_id")

    is_bad = reason != ""
    clean = df.loc[~is_bad].copy()
    quarantine = df.loc[is_bad].copy()
    quarantine["reason"] = reason.loc[is_bad]
    return clean, quarantine
