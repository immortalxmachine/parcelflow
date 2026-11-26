"""Data-quality screening.

Splits a batch of raw orders into:

* **clean**      - rows that pass every rule, ready for the warehouse.
* **quarantine** - rows that fail a rule, tagged with the reason so they can
                   be audited and fixed rather than silently dropped.

The rules check the data for genuine defects/inconsistencies - nothing is
injected. On the real Olist data the main thing they catch is a handful of
orders marked ``delivered`` that carry no delivery timestamp.

Rules enforced (first failing rule wins as the reason):
    1. required fields present (order_id, purchase_date, customer_state, status)
    2. purchase_date is a real calendar date
    3. customer_state / order_status are known reference values
    4. numeric sanity (price, freight, items non-negative when present)
    5. a delivered order must carry a delivery date (status/date consistency)
    6. duplicate order_id (keep first occurrence, quarantine the rest)
"""

from __future__ import annotations

import pandas as pd

from ..source.states import ORDER_STATUSES, STATE_CODES

REQUIRED_FIELDS = ["order_id", "purchase_date", "customer_state", "order_status"]
VALID_STATES = set(STATE_CODES)
VALID_STATUSES = set(ORDER_STATUSES)


def _blank(series: pd.Series) -> pd.Series:
    """True where a value is null or an empty/whitespace string."""
    return series.isna() | (series.astype(str).str.strip() == "")


def _neg_when_present(series: pd.Series) -> pd.Series:
    """True where a value is present (non-blank) but not a non-negative number."""
    present = ~_blank(series)
    num = pd.to_numeric(series, errors="coerce")
    return present & (num.isna() | (num < 0))


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

    # 2. purchase_date must be a real date (YYYY-MM-DD).
    parsed = pd.to_datetime(df["purchase_date"], format="%Y-%m-%d", errors="coerce")
    flag(parsed.isna(), "bad_purchase_date")

    # 3. Reference-data validity.
    flag(~df["customer_state"].isin(VALID_STATES), "unknown_customer_state")
    flag(~df["order_status"].isin(VALID_STATUSES), "unknown_order_status")

    # 4. Numeric sanity (only when a value is present; no-item orders legitimately
    #    have blank price/freight).
    flag(_neg_when_present(df["price"]), "bad_price")
    flag(_neg_when_present(df["freight_value"]), "bad_freight_value")
    flag(_neg_when_present(df["n_items"]), "bad_n_items")

    # 5. Status/date consistency: a delivered order must have a delivery date.
    delivered = df["order_status"].astype(str).str.strip() == "delivered"
    flag(delivered & _blank(df["delivered_date"]), "delivered_without_date")

    # 6. Duplicate order_id - keep the first, quarantine later copies.
    dup = df.duplicated(subset=["order_id"], keep="first")
    flag(dup, "duplicate_order_id")

    is_bad = reason != ""
    clean = df.loc[~is_bad].copy()
    quarantine = df.loc[is_bad].copy()
    quarantine["reason"] = reason.loc[is_bad]
    return clean, quarantine
