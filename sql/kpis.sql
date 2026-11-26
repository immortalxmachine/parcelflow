-- ParcelFlow KPI queries, read by the dashboard and the forecasting step.
--
-- Each query is named with a "-- name: <id>" marker and loaded by
-- parcelflow.db.sqlfile.load_named_queries(). They are intentionally written
-- in portable SQL (runs on both SQLite and PostgreSQL) and showcase CTEs and
-- window functions (AVG OVER, RANK, LAG).
--
-- "Volume" = number of orders (one row per order shipped). A hub is a
-- Brazilian customer state (dim_hub).

-- name: daily_volume_by_hub
-- Daily order volume for every hub (state).
SELECT d.date        AS date,
       h.hub_code    AS hub_code,
       h.hub_name    AS hub_name,
       COUNT(*)      AS orders
FROM fact_shipments f
JOIN dim_date d ON d.date_key = f.date_key
JOIN dim_hub  h ON h.hub_key  = f.hub_key
GROUP BY d.date, h.hub_code, h.hub_name
ORDER BY d.date, h.hub_code;

-- name: volume_7day_moving_avg
-- 7-day moving average of daily volume per hub (window function).
WITH daily AS (
    SELECT f.hub_key, d.date AS date, COUNT(*) AS orders
    FROM fact_shipments f
    JOIN dim_date d ON d.date_key = f.date_key
    GROUP BY f.hub_key, d.date
)
SELECT h.hub_code,
       daily.date,
       daily.orders,
       AVG(daily.orders) OVER (
           PARTITION BY daily.hub_key
           ORDER BY daily.date
           ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) AS moving_avg_7d
FROM daily
JOIN dim_hub h ON h.hub_key = daily.hub_key
ORDER BY h.hub_code, daily.date;

-- name: on_time_rate_by_hub
-- On-time delivery rate per hub (of delivered orders).
SELECT h.hub_code,
       h.hub_name,
       SUM(CASE WHEN f.is_on_time  THEN 1 ELSE 0 END) AS on_time,
       SUM(CASE WHEN f.is_delivered THEN 1 ELSE 0 END) AS delivered,
       ROUND(
           100.0 * SUM(CASE WHEN f.is_on_time THEN 1 ELSE 0 END)
           / NULLIF(SUM(CASE WHEN f.is_delivered THEN 1 ELSE 0 END), 0),
           2
       ) AS on_time_pct
FROM fact_shipments f
JOIN dim_hub h ON h.hub_key = f.hub_key
GROUP BY h.hub_code, h.hub_name
ORDER BY on_time_pct DESC;

-- name: hub_utilisation_rank
-- Rank hubs by total volume overall and within their region (RANK window).
WITH hub_vol AS (
    SELECT f.hub_key, COUNT(*) AS total_orders
    FROM fact_shipments f
    GROUP BY f.hub_key
)
SELECT h.hub_code,
       h.hub_name,
       h.region,
       hub_vol.total_orders,
       RANK() OVER (ORDER BY hub_vol.total_orders DESC) AS volume_rank,
       RANK() OVER (
           PARTITION BY h.region
           ORDER BY hub_vol.total_orders DESC
       ) AS region_rank
FROM hub_vol
JOIN dim_hub h ON h.hub_key = hub_vol.hub_key
ORDER BY volume_rank;

-- name: monthly_volume_trend
-- Monthly total volume with month-over-month change (CTE + LAG window).
WITH monthly AS (
    SELECT d.year, d.month, COUNT(*) AS orders
    FROM fact_shipments f
    JOIN dim_date d ON d.date_key = f.date_key
    GROUP BY d.year, d.month
)
SELECT year,
       month,
       orders,
       orders - LAG(orders) OVER (ORDER BY year, month) AS mom_change
FROM monthly
ORDER BY year, month;

-- name: daily_total_volume
-- Total daily volume across all hubs (dashboard trend line).
SELECT d.date AS date, COUNT(*) AS orders
FROM fact_shipments f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.date
ORDER BY d.date;

-- name: daily_volume_series
-- Daily volume for a single hub (:hub_code) - input to the forecaster.
SELECT d.date AS date, COUNT(*) AS orders
FROM fact_shipments f
JOIN dim_date d ON d.date_key = f.date_key
JOIN dim_hub  h ON h.hub_key  = f.hub_key
WHERE h.hub_code = :hub_code
GROUP BY d.date
ORDER BY d.date;

-- name: hub_volume_stats
-- Per-hub volume stats used to pick which states are dense enough to forecast.
-- avg_per_day is orders / (calendar span of the hub's history).
SELECT h.hub_code,
       COUNT(*)                        AS total_orders,
       COUNT(DISTINCT d.date)          AS active_days,
       MIN(d.date)                     AS first_date,
       MAX(d.date)                     AS last_date
FROM fact_shipments f
JOIN dim_date d ON d.date_key = f.date_key
JOIN dim_hub  h ON h.hub_key  = f.hub_key
GROUP BY h.hub_code
ORDER BY total_orders DESC;
