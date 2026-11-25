-- ParcelFlow warehouse transformations.
--
-- Loads the star-schema fact table from the staging table for a single
-- partition (:load_date). Dimensions are seeded separately (dim_hub and
-- dim_service are static; dim_date is populated from the dates present).
--
-- This statement is portable across SQLite and PostgreSQL:
--   * TRUE/FALSE booleans are understood by both.
--   * dimension keys are resolved by joining on natural keys.
-- Re-running is safe: the pipeline first deletes this partition's fact rows
-- (see transform.py), making the whole step idempotent.

-- name: insert_fact_for_partition
INSERT INTO fact_shipments
    (date_key, hub_key, service_key, weight_kg, distance_km,
     promised_hours, actual_hours, is_delivered, is_on_time)
SELECT
    d.date_key,
    h.hub_key,
    s.service_key,
    st.weight_kg,
    st.distance_km,
    st.promised_hours,
    st.actual_hours,
    CASE WHEN st.status = 'DELIVERED' THEN TRUE ELSE FALSE END AS is_delivered,
    CASE
        WHEN st.status = 'DELIVERED'
         AND st.actual_hours IS NOT NULL
         AND st.actual_hours <= st.promised_hours
        THEN TRUE ELSE FALSE
    END AS is_on_time
FROM stg_shipments st
JOIN dim_date    d  ON d.date         = st.ship_date
JOIN dim_hub     h  ON h.hub_code     = st.hub_code
JOIN dim_service s  ON s.service_type = st.service_type
WHERE st.load_date = :load_date;
