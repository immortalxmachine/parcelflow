# ParcelFlow — Interview Notes

20 questions an interviewer is likely to ask about this project, answered from
**this exact codebase**. File references point at where each concept lives.

---

### 1. ETL vs ELT — which is this and why?
This is **ELT**. Raw files are *extracted* to blob storage and *loaded* into
the warehouse staging table largely as-is, then *transformed* inside the
database (SQL) into the star schema. See the stage order in
`src/parcelflow/pipeline/runner.py` (`extract → load → quality → transform`),
with the transform being `sql/transforms.sql`.
**Why ELT:** pushing transformation into the warehouse lets the database engine
do set-based work at scale, keeps raw data replayable, and matches how cloud
warehouses (BigQuery, Snowflake, Redshift) are used today.

### 2. Walk me through the data flow.
Generator writes one CSV per hub per day to `raw/date=YYYY-MM-DD/HUB.csv` in
blob storage (`generate/generator.py`). `extract.read_partition` reads a day
back into a DataFrame; `quality.screen` splits clean vs bad rows;
`load.load_staging`/`load_quarantine` write them to `stg_shipments` /
`quarantine_shipments`; `transform.build_fact_for_partition` runs an
`INSERT ... SELECT` that joins staging to the dimensions and populates
`fact_shipments`. A `run_log` row records the counts.

### 3. Explain the star schema and why you used it.
`fact_shipments` (one row per shipment) references three conformed dimensions:
`dim_hub`, `dim_date`, `dim_service` (`db/schema.py`). Facts hold measures and
foreign keys; dimensions hold descriptive attributes. A star schema keeps
analytical queries simple (one join per dimension), is fast for aggregation,
and is the standard model for BI/warehouse workloads. I used **surrogate
integer keys** (`hub_key`, `date_key`, `service_key`) so the warehouse is
insulated from changes in natural/business keys.

### 4. What is `date_key` and why `yyyymmdd`?
`date_key` is a surrogate key for `dim_date` encoded as an integer `yyyymmdd`
(e.g. `20241020`). It is human-readable, sorts chronologically, makes
partition deletes trivial, and avoids storing/joining on raw date strings.
See `pipeline/dims.py::_date_row`.

### 5. What does "idempotent" mean here and how did you achieve it?
Running the pipeline for a date twice produces the **same** tables, not
duplicates. Each stage *deletes its partition, then writes it*:
`load._delete_partition` clears staging/quarantine for the `load_date`;
`transform.build_fact_for_partition` deletes `fact_shipments` for that
`date_key` before re-inserting; `run_log` keeps one row per `run_date`.
Generation is also reproducible (point 6), so re-runs converge. Tested in
`tests/test_pipeline.py::test_run_is_idempotent`.

### 6. How is the synthetic data reproducible across runs?
Each (date, hub) seeds a `random.Random` with `int(yyyymmdd) + crc32(hub_code)`
(`generator.generate_and_store`). I use **`zlib.crc32`, not Python's built-in
`hash()`**, because `hash()` of a string is randomised per process
(PYTHONHASHSEED), which would make re-runs differ. This was a real bug I caught
and fixed.

### 7. What data-quality checks do you run, and what happens to bad rows?
`pipeline/quality.py` enforces: required fields non-null, `ship_date` is a real
calendar date, `hub_code`/`service_type` are known reference values, numeric
ranges (positive weight/distance/promised hours within sane bounds), and
duplicate `shipment_id`. Bad rows are **not dropped** — they go to
`quarantine_shipments` tagged with a `reason`, so failures are auditable and
fixable. The run log reports rows in / passed / quarantined.

### 8. Why quarantine instead of dropping bad rows?
Silently dropping data hides problems and makes counts unexplainable.
Quarantining preserves the row and the reason, so you can measure data quality
over time, alert on spikes, and backfill fixes. It's the difference between
"we lost 2% of rows" and "2% failed rule X on date Y, here they are".

### 9. Explain a window function you used.
`sql/kpis.sql::volume_7day_moving_avg` computes a trailing 7-day average:
`AVG(shipments) OVER (PARTITION BY hub_key ORDER BY date ROWS BETWEEN 6
PRECEDING AND CURRENT ROW)`. The window frame (`ROWS BETWEEN 6 PRECEDING AND
CURRENT ROW`) gives each row the average of itself and the previous six days,
per hub. `hub_utilisation_rank` uses `RANK() OVER (...)` and
`monthly_volume_trend` uses `LAG()` for month-over-month change.

### 10. What is a CTE and where did you use one?
A Common Table Expression (`WITH name AS (...)`) is a named subquery that makes
a query readable and reusable within itself. `hub_utilisation_rank` first
builds a `hub_vol` CTE (total volume per hub) then ranks it; the moving-average
query builds a `daily` CTE before applying the window.

### 11. How does the forecasting work? Why SARIMA?
`forecast/forecast.py` fits **SARIMA(1,0,1)(1,1,1,7) + constant** per hub —
ARMA(1,1) terms, no regular differencing (`d=0`) with a constant level, and a
seasonal part with weekly period `m=7` and one seasonal difference (`D=1`). I
forecast 14 days ahead with an 80% confidence interval from the model variance.
**Why this order:** I first tried the textbook double-differenced
(1,1,1)(1,1,1,7); it *lost* to the seasonal-naive baseline because double
differencing makes a 14-step-ahead forecast drift. I ran a small model-selection
sweep (see `docs/architecture.md`) and `d=0 + const` kept the forecast anchored
to the series level while the ARMA terms captured the sub-monthly demand cycles
— that spec beat the baseline by ~16% MAPE. Be ready to explain that the first
model losing to naive was the finding that drove the fix.

### 12. What's the baseline and why compare against it?
The baseline is **seasonal-naive**: "next Tuesday ≈ last Tuesday"
(`seasonal_naive`). A model is only worth its complexity if it beats a trivial
baseline, so I report MAPE for both and the % improvement. This is a standard
honesty check in forecasting.

### 13. What is MAPE and why that metric?
Mean Absolute Percentage Error: `mean(|actual - predicted| / actual) * 100`
(`forecast.mape`). It's scale-free, so errors are comparable across hubs of
very different sizes, and it's intuitive ("we're off by ~X%"). Its weakness is
instability near zero actuals, so I mask zero-actual points.

### 14. How did you measure forecast accuracy honestly?
A **holdout back-test**: fit on all but the last 14 days, predict those 14, and
compare to the actuals (`evaluate_hub`). The reported MAPE is therefore
out-of-sample, not training error — the same discipline as a train/test split
in ML.

### 15. Why abstract storage behind an interface?
`storage/base.py` defines a `StorageBackend` ABC with `LocalFileStorage` and
`AzureBlobStorage` implementations (Strategy pattern). The pipeline depends
only on the interface, so switching between local filesystem (dev/CI) and Azure
Blob/Azurite (prod) is a one-line config change (`STORAGE_BACKEND`) and never
touches pipeline logic. Same idea for the DB via `DATABASE_URL`.

### 16. How does the same code run on SQLite and PostgreSQL?
All DB access is through **SQLAlchemy Core**. Schema is defined once in
`db/schema.py` and emits correct DDL per dialect (e.g. an integer PK becomes
SQLite's rowid alias or Postgres `SERIAL`). The SQL in `sql/` is written in the
portable subset both engines share (CTEs, window functions, `TRUE/FALSE`). So
`DATABASE_URL=sqlite:///...` locally and `postgresql+psycopg://...` in Docker
run identical logic.

### 17. What does Azurite give you?
Azurite is Microsoft's **Azure Blob Storage emulator**. It lets the exact Azure
SDK code path (`storage/azure_blob.py`) run locally with no cloud account, no
credentials beyond the public emulator string, and no cost — so the
"production" topology (Postgres + Blob) is fully reproducible on a laptop via
`docker compose`.

### 18. Is the Azurite connection string a leaked secret?
No. `devstoreaccount1` + its key is Microsoft's **well-known public emulator
credential**; it only works against a local Azurite instance. Real Azure
credentials go in `.env` (git-ignored) with a committed `.env.example`. See the
note in `.env.example`.

### 19. How is the pipeline scheduled / orchestrated?
`pipeline.py` is a single idempotent entrypoint
(`run --date`, `backfill`, `forecast`, `status`). `.github/workflows/
daily-pipeline.yml` runs it on a cron schedule (and on-demand). Because runs
are idempotent, a retried or overlapping run is safe. In a bigger system I'd
swap cron for Airflow/Prefect to get dependencies, retries and backfill
management — see question 20.

### 20. How would you scale this to real FedEx volumes (Spark/Databricks)?
Today one hub-day is ~thousands of parcels; at real scale it's orders of
magnitude more. I'd: (a) land raw files in a data lake (ADLS/S3) partitioned by
date, (b) replace the pandas load + SQL transform with **Spark/Databricks**
jobs (or dbt on a cloud warehouse) for distributed, set-based transforms, (c)
orchestrate with Airflow/Prefect for retries and backfills, (d) keep the star
schema but materialise it in a columnar warehouse, and (e) train forecasts per
hub in parallel. The architecture (ELT, star schema, quarantine, idempotency,
backend abstraction) stays the same — only the engines change. The
`VOLUME_SCALE` knob in `config.py` is a nod to this: the same code generates a
laptop-sized or a full-scale dataset.

---

## Three things most likely to be grilled

1. **Idempotency & reproducibility** (Q5, Q6) — be ready to explain the
   delete-then-write pattern and the `crc32` seeding bug.
2. **Star schema + window-function SQL** (Q3, Q9, Q10) — expect to read a query
   aloud and explain the window frame.
3. **SARIMA vs baseline + honest MAPE** (Q11–Q14) — expect "why not just a
   moving average?" and "how do you know it's not overfit?".
