"""Tests for the local storage backend (the Strategy used in dev/CI)."""

from __future__ import annotations

from parcelflow.storage.local import LocalFileStorage


def test_write_read_roundtrip(tmp_path):
    store = LocalFileStorage(str(tmp_path))
    uri = store.write_bytes("raw/date=2024-01-01/CHN.csv", b"hello")
    assert store.read_bytes("raw/date=2024-01-01/CHN.csv") == b"hello"
    assert "CHN.csv" in uri


def test_exists_and_list(tmp_path):
    store = LocalFileStorage(str(tmp_path))
    assert store.exists("missing") is False
    store.write_bytes("raw/date=2024-01-01/CHN.csv", b"a")
    store.write_bytes("raw/date=2024-01-01/MUM.csv", b"b")
    store.write_bytes("raw/date=2024-01-02/CHN.csv", b"c")

    keys = store.list_keys("raw/date=2024-01-01/")
    assert keys == [
        "raw/date=2024-01-01/CHN.csv",
        "raw/date=2024-01-01/MUM.csv",
    ]
    assert store.exists("raw/date=2024-01-01/CHN.csv") is True


def test_overwrite_is_idempotent(tmp_path):
    store = LocalFileStorage(str(tmp_path))
    store.write_bytes("k.csv", b"first")
    store.write_bytes("k.csv", b"second")
    assert store.read_bytes("k.csv") == b"second"
