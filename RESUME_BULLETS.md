# ParcelFlow — Resume Bullets

Every number below is **measured from this repo** (the warehouse and
`metrics.json`), not estimated. Each bullet: *action verb + what + how +
measurable result*, ≤ 25 words.

---

- Built an idempotent ELT pipeline ingesting **695K synthetic shipment rows** across **731 daily partitions** and **15 hubs** into a PostgreSQL/SQLite star-schema warehouse.

- Engineered a 14-day SARIMA volume forecaster that **beat a seasonal-naive baseline by ~16% MAPE** (14.1% vs 16.8%) via holdout back-testing and model selection.

- Added a data-quality stage that quarantined **16,081 bad rows (2.3%)** with reasons instead of dropping them, plus a run log for full pipeline observability.

- Designed swappable storage/DB backends (local↔Azure Blob, SQLite↔Postgres) so the same code runs laptop-local or cloud, covered by **21 automated tests** in CI.

---

### Notes for tailoring
- Pick the 3 bullets most relevant to the role (the brief asks for 3).
- "synthetic" is stated honestly; keep it — interviewers respect it.
- If space is tight, the forecasting and ELT bullets are the strongest two.
- Swap in a live dashboard URL only after you actually deploy (see `docs/deploy.md`).
