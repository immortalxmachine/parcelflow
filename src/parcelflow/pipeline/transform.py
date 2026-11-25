"""Transform step: load the star-schema fact table from staging.

Idempotent per partition: the fact rows for the load date are deleted before
being re-inserted, so re-running a date never duplicates facts. The actual
INSERT ... SELECT lives in ``sql/transforms.sql`` (portable SQL), keeping the
transformation logic out of Python.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Engine, text

from ..db.schema import fact_shipments
from ..db.sqlfile import get_query


def _date_key(load_date: str) -> int:
    return int(datetime.strptime(load_date, "%Y-%m-%d").strftime("%Y%m%d"))


def build_fact_for_partition(engine: Engine, load_date: str) -> int:
    """(Re)build ``fact_shipments`` for ``load_date``. Returns rows inserted."""
    insert_sql = get_query("transforms.sql", "insert_fact_for_partition")
    date_key = _date_key(load_date)
    with engine.begin() as conn:
        # Idempotency: clear this date's facts first.
        conn.execute(
            fact_shipments.delete().where(fact_shipments.c.date_key == date_key)
        )
        conn.execute(text(insert_sql), {"load_date": load_date})
        count = conn.execute(
            text("SELECT COUNT(*) FROM fact_shipments WHERE date_key = :k"),
            {"k": date_key},
        ).scalar_one()
    return int(count)
