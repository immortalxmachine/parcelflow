# ParcelFlow — Resume Bullets

Every number below is **measured from this repo** (the warehouse and
`metrics.json`), not estimated. Each bullet: *action verb + what + how +
measurable result*, ≤ 25 words.

---

- Built an idempotent ELT pipeline ingesting **98.5K real Olist e-commerce orders** across **595 daily partitions** and **27 Brazilian states** into a PostgreSQL/SQLite star-schema warehouse.

- Engineered a 14-day SARIMA order-volume forecaster that **beat a seasonal-naive baseline by ~40% MAPE** (25.1% vs 42.1%) via holdout back-testing across the 5 highest-volume states.

- Added a data-quality stage that quarantined inconsistent orders (delivered-without-date) with reasons instead of dropping them, plus a run log for full pipeline observability.

- Designed swappable storage/DB backends (local↔Azure Blob, SQLite↔Postgres) so the same code runs laptop-local or cloud, covered by **23 automated tests** in CI.

---

### Notes for tailoring
- Pick the 3 bullets most relevant to the role (the brief asks for 3).
- The data is **real** (public Olist dataset, cited + licensed) — say so; it is
  stronger than a synthetic dataset and interviewers respect it.
- If space is tight, the forecasting and ELT bullets are the strongest two.
- Swap in a live dashboard URL only after you actually deploy (see `docs/deploy.md`).
