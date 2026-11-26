"""Tests for the forecasting module."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from parcelflow.forecast import forecast as fc
from parcelflow.pipeline import runner


def test_mape_basic():
    actual = np.array([100, 200, 400])
    pred = np.array([110, 180, 400])
    # errors: 10%, 10%, 0% -> mean 6.667%
    assert round(fc.mape(actual, pred), 2) == 6.67


def test_mape_ignores_zero_actuals():
    assert fc.mape(np.array([0, 100]), np.array([5, 90])) == 10.0


def test_seasonal_naive_repeats_week():
    idx = pd.date_range("2024-01-01", periods=14, freq="D")
    train = pd.Series(range(14), index=idx, dtype="float64")
    preds = fc.seasonal_naive(train, horizon=7, season=7)
    # Next 7 days should repeat the last 7 observed values (7..13).
    assert list(preds) == [7, 8, 9, 10, 11, 12, 13]


# A dense state (São Paulo) over a 45-day window inside the Olist data.
DENSE_HUB = "SP"
START = date(2018, 1, 2)


def _backfill(engine, storage, settings, days: int):
    for i in range(days):
        runner.run_for_date(
            START + timedelta(days=i), engine=engine, storage=storage, settings=settings
        )


def test_evaluate_hub_returns_finite_mape(engine, storage, settings):
    _backfill(engine, storage, settings, days=45)
    metrics = fc.evaluate_hub(engine, DENSE_HUB, holdout=7)
    assert metrics.hub_code == DENSE_HUB
    assert metrics.n_days == 45
    assert np.isfinite(metrics.mape_sarima)
    assert np.isfinite(metrics.mape_naive)


def test_forecast_future_shape(engine, storage, settings):
    _backfill(engine, storage, settings, days=45)
    out = fc.forecast_future(engine, DENSE_HUB, horizon=14)
    assert len(out) == 14
    assert list(out.columns) == ["date", "forecast", "lower", "upper"]
    # Confidence band should bracket the point forecast.
    assert (out["lower"] <= out["forecast"]).all()
    assert (out["forecast"] <= out["upper"]).all()


def test_forecastable_hubs_selects_dense_states(engine, storage, settings):
    _backfill(engine, storage, settings, days=45)
    # Over this window SP is dense (~60+/day) and should be selected; a tiny
    # state like Roraima (RR) should not clear the threshold.
    hubs = fc.forecastable_hubs(engine, min_avg_per_day=3.0, min_days=30)
    assert DENSE_HUB in hubs
    assert "RR" not in hubs
