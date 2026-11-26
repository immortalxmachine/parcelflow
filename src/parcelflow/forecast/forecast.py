"""Parcel-volume forecasting.

For each hub we forecast the next ``horizon`` days of daily parcel volume with
a **SARIMA** model (seasonal ARIMA, weekly season m=7) and compare it against a
**seasonal-naive** baseline (tomorrow looks like the same weekday last week).
Model quality is reported as **MAPE** (mean absolute percentage error) on a
held-out tail of the series, so the numbers are honest out-of-sample errors.

Reporting both a model and a naive baseline is deliberate: a forecasting model
is only worth its complexity if it beats the naive baseline.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text

from ..db.sqlfile import get_query

SEASON = 7          # weekly seasonality
DEFAULT_HORIZON = 14
HOLDOUT = 14        # days held out to measure error

# Model order chosen by validation (see docs/architecture.md): no regular
# differencing (d=0) with a constant keeps the 14-day forecast anchored to the
# series level, while seasonal differencing (D=1) handles the strong weekly
# cycle in the order data and the ARMA(1,1) terms capture short-run
# autocorrelation. Aggressive double differencing (d=1,D=1) drifts over a
# 14-day horizon and loses to the seasonal-naive baseline; this spec beats it.
ORDER = (1, 0, 1)
SEASONAL_ORDER = (1, 1, 1, SEASON)
TREND = "c"
MODEL_NAME = "SARIMA(1,0,1)(1,1,1,7)+c"


@dataclass
class HubForecastMetrics:
    hub_code: str
    n_days: int
    mape_sarima: float
    mape_naive: float
    improvement_pct: float  # how much SARIMA beats the baseline


def load_series(engine: Engine, hub_code: str) -> pd.Series:
    """Load a hub's daily volume as a date-indexed, gap-free integer series."""
    sql = get_query("kpis.sql", "daily_volume_series")
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"hub_code": hub_code}).fetchall()
    if not rows:
        return pd.Series(dtype="float64")
    s = pd.Series(
        [r[1] for r in rows],
        index=pd.to_datetime([r[0] for r in rows]),
        dtype="float64",
    )
    s = s.sort_index()
    # Fill any missing calendar days so the seasonal model sees a regular grid.
    full_idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full_idx).interpolate().ffill().bfill()


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean absolute percentage error (%). Ignores any zero-actual points."""
    actual = np.asarray(actual, dtype="float64")
    predicted = np.asarray(predicted, dtype="float64")
    mask = actual != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def seasonal_naive(train: pd.Series, horizon: int, season: int = SEASON) -> np.ndarray:
    """Forecast each future day as the value ``season`` days earlier."""
    history = train.to_numpy()
    preds = [history[-season + (i % season)] for i in range(horizon)]
    return np.array(preds, dtype="float64")


def _fit_sarima(train: pd.Series, season: int = SEASON):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # convergence/frequency warnings are noisy
        model = SARIMAX(
            train,
            order=ORDER,
            seasonal_order=(SEASONAL_ORDER[0], SEASONAL_ORDER[1], SEASONAL_ORDER[2], season),
            trend=TREND,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        return model.fit(disp=False)


def sarima_forecast(
    train: pd.Series, horizon: int, season: int = SEASON
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (mean, lower, upper) SARIMA forecasts for ``horizon`` days."""
    fitted = _fit_sarima(train, season)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fc = fitted.get_forecast(steps=horizon)
    mean = np.asarray(fc.predicted_mean, dtype="float64")
    ci = np.asarray(fc.conf_int(alpha=0.2), dtype="float64")  # 80% interval
    return mean, ci[:, 0], ci[:, 1]


def evaluate_hub(
    engine: Engine, hub_code: str, holdout: int = HOLDOUT, season: int = SEASON
) -> HubForecastMetrics:
    """Back-test SARIMA vs the baseline on the last ``holdout`` days."""
    series = load_series(engine, hub_code)
    train, test = series.iloc[:-holdout], series.iloc[-holdout:]

    naive_pred = seasonal_naive(train, holdout, season)
    sarima_pred, _, _ = sarima_forecast(train, holdout, season)

    m_naive = mape(test.to_numpy(), naive_pred)
    m_sarima = mape(test.to_numpy(), sarima_pred)
    improvement = (m_naive - m_sarima) / m_naive * 100 if m_naive else float("nan")

    return HubForecastMetrics(
        hub_code=hub_code,
        n_days=len(series),
        mape_sarima=round(m_sarima, 3),
        mape_naive=round(m_naive, 3),
        improvement_pct=round(improvement, 2),
    )


def forecast_future(
    engine: Engine, hub_code: str, horizon: int = DEFAULT_HORIZON, season: int = SEASON
) -> pd.DataFrame:
    """Fit on all history and forecast the next ``horizon`` days (for the UI)."""
    series = load_series(engine, hub_code)
    mean, lower, upper = sarima_forecast(series, horizon, season)
    future_idx = pd.date_range(
        series.index.max() + pd.Timedelta(days=1), periods=horizon, freq="D"
    )
    return pd.DataFrame(
        {
            "date": future_idx,
            "forecast": np.round(mean, 1),
            "lower": np.round(lower, 1),
            "upper": np.round(upper, 1),
        }
    )


def forecastable_hubs(
    engine: Engine, min_avg_per_day: float = 8.0, min_days: int = 120
) -> list[str]:
    """Return hub codes dense enough to forecast a daily series on.

    Daily counts carry Poisson sampling noise with coefficient of variation
    ~1/sqrt(mean): a state averaging 3 orders/day has a ~58% noise floor, so no
    model can forecast it well. We keep only states averaging at least
    ``min_avg_per_day`` orders (default 8 -> noise floor <= ~35%) over a history
    of at least ``min_days`` days; the rest are stored but not forecast.
    Returned most-active first.
    """
    sql = get_query("kpis.sql", "hub_volume_stats")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    out: list[str] = []
    for r in rows:
        hub_code, total, _active, first_date, last_date = r[0], r[1], r[2], r[3], r[4]
        span = (
            pd.Timestamp(last_date) - pd.Timestamp(first_date)
        ).days + 1
        if span >= min_days and total / span >= min_avg_per_day:
            out.append(hub_code)
    return out


def evaluate_all(engine: Engine, hub_codes: list[str], holdout: int = HOLDOUT) -> dict:
    """Back-test every hub and build a metrics dict (for metrics.json)."""
    per_hub = []
    for code in hub_codes:
        try:
            per_hub.append(evaluate_hub(engine, code, holdout))
        except Exception as exc:  # keep going; record which hub failed
            per_hub.append(
                HubForecastMetrics(code, 0, float("nan"), float("nan"), float("nan"))
            )
            print(f"  ! forecast failed for {code}: {exc}")

    valid = [m for m in per_hub if not np.isnan(m.mape_sarima)]
    avg_sarima = round(float(np.mean([m.mape_sarima for m in valid])), 3) if valid else None
    avg_naive = round(float(np.mean([m.mape_naive for m in valid])), 3) if valid else None
    avg_impr = (
        round((avg_naive - avg_sarima) / avg_naive * 100, 2)
        if avg_sarima is not None and avg_naive
        else None
    )
    return {
        "model": MODEL_NAME,
        "baseline": "seasonal_naive(m=7)",
        "metric": "MAPE_percent",
        "holdout_days": holdout,
        "avg_mape_sarima": avg_sarima,
        "avg_mape_naive": avg_naive,
        "avg_improvement_pct": avg_impr,
        "per_hub": [m.__dict__ for m in per_hub],
    }
