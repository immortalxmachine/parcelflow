"""Tests for the synthetic data generator."""

from __future__ import annotations

import random
from datetime import date

from parcelflow.generate import generator as gen
from parcelflow.generate.hubs import HUBS_BY_CODE


def _rows(d: date, hub_code: str, seed: int = 1):
    rng = random.Random(seed)
    return gen.generate_day_rows(d, HUBS_BY_CODE[hub_code], rng, volume_scale=0.05)


def test_generate_day_rows_schema():
    rows = _rows(date(2024, 3, 15), "CHN")
    assert rows, "should generate at least one row"
    assert set(rows[0]) == set(gen.COLUMNS)
    assert all(r["hub_code"] == "CHN" for r in rows)
    assert all(r["ship_date"] == "2024-03-15" for r in rows)


def test_generation_is_reproducible():
    # Same date + hub => identical data (stable hashing). This is what makes
    # the pipeline idempotent across processes.
    import tempfile

    from parcelflow.storage.local import LocalFileStorage

    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        sa, sb = LocalFileStorage(a), LocalFileStorage(b)
        gen.generate_and_store(date(2024, 3, 15), sa, volume_scale=0.02)
        gen.generate_and_store(date(2024, 3, 15), sb, volume_scale=0.02)
        key = gen.raw_key(date(2024, 3, 15), "CHN")
        assert sa.read_bytes(key) == sb.read_bytes(key)


def test_festival_peak_exceeds_monsoon():
    # Late-October festival volume should exceed a monsoon-month day for a hub.
    festival = _rows(date(2024, 10, 25), "DEL")
    monsoon = _rows(date(2024, 7, 15), "DEL")
    assert len(festival) > len(monsoon)


def test_dirty_injection_adds_rows():
    rng = random.Random(5)
    clean = gen.generate_day_rows(date(2024, 3, 15), HUBS_BY_CODE["MUM"], rng, 0.05)
    dirtied = gen._inject_dirty_rows(list(clean), rng, dirty_rate=0.2)
    assert len(dirtied) > len(clean)
