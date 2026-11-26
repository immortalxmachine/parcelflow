"""Tests for data-quality screening."""

from __future__ import annotations

import pandas as pd

from parcelflow.pipeline.quality import screen


def _base_row(**over):
    row = {
        "order_id": "order-0001",
        "purchase_date": "2017-11-24",
        "customer_state": "SP",
        "order_status": "delivered",
        "price": 129.9,
        "freight_value": 15.1,
        "n_items": 1,
        "delivery_days": 8,
        "delivered_date": "2017-12-02",
        "estimated_date": "2017-12-15",
    }
    row.update(over)
    return row


def test_all_clean_rows_pass():
    df = pd.DataFrame([_base_row(order_id=f"x{i}") for i in range(5)])
    clean, quarantine = screen(df)
    assert len(clean) == 5
    assert quarantine.empty


def test_no_item_order_is_clean():
    # Orders with no items legitimately have blank price/freight - not a defect.
    df = pd.DataFrame([
        _base_row(order_id="ni", order_status="unavailable", price="",
                  freight_value="", n_items=0, delivered_date="", delivery_days=""),
    ])
    clean, quarantine = screen(df)
    assert len(clean) == 1
    assert quarantine.empty


def test_each_defect_is_quarantined_with_reason():
    df = pd.DataFrame([
        _base_row(order_id="ok"),
        _base_row(order_id="n1", customer_state=""),
        _base_row(order_id="n2", price=-3),
        _base_row(order_id="n3", purchase_date="0000-99-99"),
        _base_row(order_id="n4", order_status="ROCKET"),
        _base_row(order_id="n5", order_status="delivered", delivered_date=""),
    ])
    clean, quarantine = screen(df)
    assert len(clean) == 1
    reasons = set(quarantine["reason"])
    assert reasons == {
        "null_customer_state", "bad_price", "bad_purchase_date",
        "unknown_order_status", "delivered_without_date",
    }


def test_duplicate_order_id_quarantined():
    df = pd.DataFrame([_base_row(order_id="dup"), _base_row(order_id="dup")])
    clean, quarantine = screen(df)
    assert len(clean) == 1  # first kept
    assert list(quarantine["reason"]) == ["duplicate_order_id"]


def test_empty_input():
    clean, quarantine = screen(pd.DataFrame())
    assert clean.empty and quarantine.empty
