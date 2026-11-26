"""Tests for the Olist real-data source loader."""

from __future__ import annotations

from datetime import date

from parcelflow.source import olist
from parcelflow.source.states import STATE_CODES


def test_load_orders_schema_and_window(settings):
    df = olist.load_orders(settings)
    assert not df.empty
    for col in olist.COLUMNS:
        assert col in df.columns
    # Every purchase date must fall inside the documented dense window.
    assert df["purchase_date"].min() >= olist.WINDOW_START.isoformat()
    assert df["purchase_date"].max() <= olist.WINDOW_END.isoformat()


def test_available_window(settings):
    start, end = olist.available_window(settings)
    assert start >= olist.WINDOW_START
    assert end <= olist.WINDOW_END
    assert start < end


def test_write_partition_only_nonempty_states(settings, storage):
    # Black Friday 2017 is a dense day with many states present.
    d = date(2017, 11, 24)
    keys = olist.write_partition(d, storage, settings)
    assert keys, "expected at least one state file"
    # Keys are partitioned by date, one CSV per destination state.
    for key in keys:
        assert key.startswith(f"raw/date={d.isoformat()}/")
        state = key.rsplit("/", 1)[1].removesuffix(".csv")
        assert state in STATE_CODES


def test_write_partition_is_idempotent(settings):
    import tempfile

    from parcelflow.storage.local import LocalFileStorage

    d = date(2017, 11, 24)
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        sa, sb = LocalFileStorage(a), LocalFileStorage(b)
        olist.write_partition(d, sa, settings)
        olist.write_partition(d, sb, settings)
        key = olist.raw_key(d, "SP")
        assert sa.read_bytes(key) == sb.read_bytes(key)
