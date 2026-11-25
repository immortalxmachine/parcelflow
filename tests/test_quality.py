"""Tests for data-quality screening."""

from __future__ import annotations

import pandas as pd

from parcelflow.pipeline.quality import screen


def _base_row(**over):
    row = {
        "shipment_id": "CHN-2024-03-15-00001",
        "ship_date": "2024-03-15",
        "hub_code": "CHN",
        "service_type": "EXPRESS",
        "weight_kg": 2.5,
        "distance_km": 300.0,
        "promised_hours": 24.0,
        "actual_hours": 20.0,
        "status": "DELIVERED",
    }
    row.update(over)
    return row


def test_all_clean_rows_pass():
    df = pd.DataFrame([_base_row(shipment_id=f"x{i}") for i in range(5)])
    clean, quarantine = screen(df)
    assert len(clean) == 5
    assert quarantine.empty


def test_each_defect_is_quarantined_with_reason():
    df = pd.DataFrame([
        _base_row(shipment_id="ok"),
        _base_row(shipment_id="n1", hub_code=""),
        _base_row(shipment_id="n2", weight_kg=-3),
        _base_row(shipment_id="n3", ship_date="0000-99-99"),
        _base_row(shipment_id="n4", service_type="ROCKET"),
    ])
    clean, quarantine = screen(df)
    assert len(clean) == 1
    reasons = set(quarantine["reason"])
    assert reasons == {
        "null_hub_code", "bad_weight_kg", "bad_ship_date", "unknown_service_type",
    }


def test_duplicate_shipment_id_quarantined():
    df = pd.DataFrame([_base_row(shipment_id="dup"), _base_row(shipment_id="dup")])
    clean, quarantine = screen(df)
    assert len(clean) == 1  # first kept
    assert list(quarantine["reason"]) == ["duplicate_shipment_id"]


def test_empty_input():
    clean, quarantine = screen(pd.DataFrame())
    assert clean.empty and quarantine.empty
