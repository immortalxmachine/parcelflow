"""Synthetic daily shipment generator.

Produces one CSV file per day per hub (``date=YYYY-MM-DD/<hub>.csv``), each row
representing one shipment. The generated series embeds realistic structure so
the forecasting model has something meaningful to learn:

* **Weekly seasonality** - weekdays busier than weekends.
* **Festival peaks**      - a Diwali/October-November uplift.
* **Monsoon dip**         - lower volumes in the June-September monsoon.
* **Hub scale**           - each hub has its own base volume.
* **Dirty rows**          - a small, controlled fraction of null/duplicate/bad
                            rows so the data-quality stage has real work to do.

All data is SYNTHETIC. See the README.
"""

from __future__ import annotations

import csv
import io
import math
import random
import zlib
from datetime import date, datetime, timedelta

from .hubs import HUBS, SERVICE_MIX, SERVICE_TYPES, Hub

# CSV columns emitted for every shipment row.
COLUMNS = [
    "shipment_id",
    "ship_date",
    "hub_code",
    "service_type",
    "weight_kg",
    "distance_km",
    "promised_hours",
    "actual_hours",
    "status",
]

STATUSES = ["DELIVERED", "IN_TRANSIT", "EXCEPTION"]


def _weekly_factor(d: date) -> float:
    """Weekday/weekend multiplier. Mon-Fri busy, Sat medium, Sun quiet."""
    # Monday=0 ... Sunday=6
    return {0: 1.05, 1: 1.08, 2: 1.06, 3: 1.07, 4: 1.10, 5: 0.80, 6: 0.60}[d.weekday()]


def _festival_factor(d: date) -> float:
    """Diwali/festival-season uplift, peaking in late October.

    Modelled as a smooth bump centred on day-of-year ~298 (late Oct) so the
    series shows a clear, learnable annual peak without a hard spike.
    """
    doy = d.timetuple().tm_yday
    peak = 298  # ~ late October
    spread = 22.0
    bump = math.exp(-((doy - peak) ** 2) / (2 * spread**2))
    return 1.0 + 0.55 * bump  # up to +55% at the peak


def _monsoon_factor(d: date) -> float:
    """Monsoon dip across June-September (months 6-9)."""
    return 0.85 if d.month in (6, 7, 8, 9) else 1.0


def _expected_volume(hub: Hub, d: date) -> float:
    return (
        hub.base_volume
        * _weekly_factor(d)
        * _festival_factor(d)
        * _monsoon_factor(d)
    )


def _service_for(rng: random.Random) -> str:
    return rng.choices(SERVICE_TYPES, weights=SERVICE_MIX, k=1)[0]


def _promised_hours(service: str, distance_km: float) -> float:
    """Promised transit time depends on service tier and distance."""
    base = {"EXPRESS": 18, "STANDARD": 36, "ECONOMY": 60}[service]
    return round(base + distance_km / 60.0, 1)


def _actual_hours(rng: random.Random, promised: float, d: date) -> float:
    """Actual transit time as a ratio of promised time.

    On a normal day the ratio centres near 0.90 (most parcels beat the promise,
    so on-time ~85%). Festival peaks and monsoon add "stress" that pushes the
    ratio above 1.0, so on-time rates dip during those periods - exactly the
    seasonal signal the dashboard and forecaster are meant to surface.
    """
    stress = (_festival_factor(d) - 1.0) + (1.0 - _monsoon_factor(d))
    ratio_mean = 0.90 + 0.35 * stress
    ratio = rng.gauss(ratio_mean, 0.11)
    return round(max(1.0, promised * max(0.3, ratio)), 1)


def generate_day_rows(
    d: date, hub: Hub, rng: random.Random, volume_scale: float = 1.0
) -> list[dict]:
    """Generate all shipment rows for one hub on one day.

    ``volume_scale`` downscales the stored row count (see ``VOLUME_SCALE`` in
    config) without changing the seasonal shape of the series.
    """
    expected = _expected_volume(hub, d) * volume_scale
    # Poisson-like count via Gaussian approximation, floored at a sane minimum.
    count = max(20, int(rng.gauss(expected, expected * 0.08)))

    rows: list[dict] = []
    for i in range(count):
        service = _service_for(rng)
        distance = round(rng.uniform(80, 2400), 1)
        weight = round(rng.lognormvariate(0.2, 0.7) + 0.2, 2)  # skewed, >0
        promised = _promised_hours(service, distance)
        actual = _actual_hours(rng, promised, d)
        status = rng.choices(STATUSES, weights=[0.93, 0.05, 0.02], k=1)[0]
        # Only delivered shipments have a meaningful actual time.
        if status != "DELIVERED":
            actual = ""
        rows.append(
            {
                "shipment_id": f"{hub.code}-{d.isoformat()}-{i:05d}",
                "ship_date": d.isoformat(),
                "hub_code": hub.code,
                "service_type": service,
                "weight_kg": weight,
                "distance_km": distance,
                "promised_hours": promised,
                "actual_hours": actual,
                "status": status,
            }
        )
    return rows


def _inject_dirty_rows(rows: list[dict], rng: random.Random, dirty_rate: float) -> list[dict]:
    """Corrupt a small fraction of rows so DQ checks have real defects to find.

    Defects injected (each row at most one):
      * null hub_code or service_type
      * negative / zero weight
      * malformed date
      * exact duplicate of another row
    """
    if not rows:
        return rows
    n_dirty = int(len(rows) * dirty_rate)
    for _ in range(n_dirty):
        kind = rng.choice(["null", "bad_weight", "bad_date", "duplicate"])
        idx = rng.randrange(len(rows))
        row = dict(rows[idx])  # copy so duplicates are independent dicts
        if kind == "null":
            row[rng.choice(["hub_code", "service_type"])] = ""
            rows.append(row)
        elif kind == "bad_weight":
            row["weight_kg"] = rng.choice([-1.5, 0, -99])
            rows.append(row)
        elif kind == "bad_date":
            row["ship_date"] = "0000-99-99"
            rows.append(row)
        elif kind == "duplicate":
            rows.append(row)  # identical shipment_id => duplicate
    rng.shuffle(rows)
    return rows


def rows_to_csv(rows: list[dict]) -> bytes:
    """Serialise rows to CSV bytes (UTF-8)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def raw_key(d: date, hub_code: str) -> str:
    """Blob key for one hub's file on one day, partitioned by date."""
    return f"raw/date={d.isoformat()}/{hub_code}.csv"


def generate_and_store(
    d: date,
    storage,
    *,
    hubs: list[Hub] | None = None,
    seed: int | None = None,
    dirty_rate: float = 0.015,
    volume_scale: float = 1.0,
) -> list[str]:
    """Generate one day of data for all hubs and write it to ``storage``.

    A deterministic per-day seed makes generation reproducible and makes the
    whole pipeline idempotent: regenerating a date yields the same data.
    Returns the list of blob keys written.
    """
    hubs = hubs or HUBS
    if seed is None:
        # Deterministic seed derived from the date => reproducible re-runs.
        seed = int(d.strftime("%Y%m%d"))

    keys: list[str] = []
    for hub in hubs:
        # zlib.crc32 is a STABLE hash (unlike builtin hash(), which is salted
        # per process). This keeps generation reproducible across runs, which
        # is what makes the whole pipeline idempotent.
        hub_offset = zlib.crc32(hub.code.encode()) % 10_000
        rng = random.Random(seed + hub_offset)
        rows = generate_day_rows(d, hub, rng, volume_scale=volume_scale)
        rows = _inject_dirty_rows(rows, rng, dirty_rate)
        key = raw_key(d, hub.code)
        storage.write_bytes(key, rows_to_csv(rows))
        keys.append(key)
    return keys


def date_range(start: date, end: date):
    """Yield every date from ``start`` to ``end`` inclusive."""
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def default_window(years: int = 2, end: date | None = None) -> tuple[date, date]:
    """Return a (start, end) window of ``years`` ending at ``end`` (default today)."""
    end = end or datetime.utcnow().date()
    start = end - timedelta(days=365 * years)
    return start, end
