"""ParcelFlow Streamlit dashboard.

Reads the warehouse (star schema) directly via the project's KPI queries and
visualises:

* **KPI cards**      - total shipments, hubs, overall on-time %, quarantine rate
* **Volume trend**   - daily total volume with a 7-day moving average
* **Hub comparison** - total volume per hub, coloured by region
* **Forecast**       - 14-day SARIMA forecast vs recent actuals, with an 80%
                       confidence band

Run with:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

# Make the src package importable when run via `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parcelflow.db.engine import get_engine  # noqa: E402
from parcelflow.db.schema import create_all  # noqa: E402
from parcelflow.db.sqlfile import get_query  # noqa: E402
from parcelflow.forecast.forecast import forecast_future, load_series  # noqa: E402
from parcelflow.generate.hubs import HUBS  # noqa: E402

st.set_page_config(page_title="ParcelFlow", page_icon="📦", layout="wide")

REGION_COLORS = {
    "South": "#2563eb", "West": "#16a34a", "North": "#d97706",
    "East": "#dc2626", "Central": "#7c3aed",
}


@st.cache_resource
def _engine():
    eng = get_engine()
    create_all(eng)
    return eng


@st.cache_data(ttl=300)
def _query_df(name: str, params: dict | None = None) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text(get_query("kpis.sql", name)), conn, params=params or {})


@st.cache_data(ttl=300)
def _has_data() -> bool:
    with _engine().connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM fact_shipments")).scalar_one() > 0


@st.cache_data(ttl=300)
def _forecast_df(hub_code: str, horizon: int) -> pd.DataFrame:
    return forecast_future(_engine(), hub_code, horizon=horizon)


@st.cache_data(ttl=300)
def _series(hub_code: str) -> pd.Series:
    return load_series(_engine(), hub_code)


def kpi_cards() -> None:
    daily = _query_df("daily_total_volume")
    ontime = _query_df("on_time_rate_by_hub")
    total = int(daily["shipments"].sum())
    delivered = int(ontime["delivered"].sum())
    on_time = int(ontime["on_time"].sum())
    on_time_pct = round(100 * on_time / delivered, 1) if delivered else 0.0

    with _engine().connect() as conn:
        quarantined = conn.execute(text("SELECT COUNT(*) FROM quarantine_shipments")).scalar_one()
    staged = total  # fact rows == cleaned shipments
    quarantine_pct = round(100 * quarantined / (staged + quarantined), 2) if staged else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total shipments", f"{total:,}")
    c2.metric("Hubs", f"{len(HUBS)}")
    c3.metric("Overall on-time %", f"{on_time_pct}%")
    c4.metric("Quarantine rate", f"{quarantine_pct}%")


def volume_trend() -> None:
    st.subheader("Daily volume trend")
    daily = _query_df("daily_total_volume")
    if daily.empty:
        st.info("No data yet.")
        return
    daily["date"] = pd.to_datetime(daily["date"])
    daily["ma7"] = daily["shipments"].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_scatter(x=daily["date"], y=daily["shipments"], name="Daily",
                    mode="lines", line=dict(color="#94a3b8", width=1))
    fig.add_scatter(x=daily["date"], y=daily["ma7"], name="7-day avg",
                    mode="lines", line=dict(color="#2563eb", width=2.5))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig, use_container_width=True)


def hub_comparison() -> None:
    st.subheader("Hub comparison - total volume")
    rank = _query_df("hub_utilisation_rank")
    if rank.empty:
        st.info("No data yet.")
        return
    rank = rank.sort_values("total_shipments", ascending=True)
    colors = [REGION_COLORS.get(r, "#64748b") for r in rank["region"]]
    fig = go.Figure(go.Bar(
        x=rank["total_shipments"], y=rank["hub_name"], orientation="h",
        marker_color=colors,
        text=rank["region"], textposition="auto",
    ))
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title="Total shipments")
    st.plotly_chart(fig, use_container_width=True)


def forecast_section() -> None:
    st.subheader("14-day volume forecast (SARIMA)")
    codes = {h.name: h.code for h in HUBS}
    name = st.selectbox("Hub", list(codes), index=0)
    horizon = st.slider("Forecast horizon (days)", 7, 28, 14, step=7)
    code = codes[name]

    with st.spinner("Fitting SARIMA model..."):
        series = _series(code)
        fc = _forecast_df(code, horizon)

    recent = series.iloc[-60:]  # show last ~2 months of history for context
    fig = go.Figure()
    fig.add_scatter(x=recent.index, y=recent.values, name="Actual",
                    mode="lines", line=dict(color="#334155", width=2))
    # Confidence band (drawn as an upper line + filled area down to the lower).
    fig.add_scatter(x=fc["date"], y=fc["upper"], name="Upper 80%",
                    mode="lines", line=dict(width=0), showlegend=False)
    fig.add_scatter(x=fc["date"], y=fc["lower"], name="80% interval",
                    mode="lines", line=dict(width=0),
                    fill="tonexty", fillcolor="rgba(37,99,235,0.18)")
    fig.add_scatter(x=fc["date"], y=fc["forecast"], name="Forecast",
                    mode="lines", line=dict(color="#2563eb", width=2.5, dash="dash"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Dashed line = forecast; shaded band = 80% confidence interval.")


def main() -> None:
    st.title("📦 ParcelFlow")
    st.caption("Cloud ELT pipeline + parcel-volume forecasting · synthetic data")

    if not _has_data():
        st.warning(
            "No warehouse data found. Run the pipeline first:\n\n"
            "`python pipeline.py backfill --years 2`"
        )
        return

    kpi_cards()
    st.divider()
    left, right = st.columns(2)
    with left:
        volume_trend()
    with right:
        hub_comparison()
    st.divider()
    forecast_section()


if __name__ == "__main__":
    main()
