-- ParcelFlow warehouse transformations.
--
-- Loads the star-schema fact table from the staging table for a single
-- partition (:load_date). Dimensions are seeded separately (dim_hub and
-- dim_order_status are static; dim_date is populated from the dates present).
--
-- This statement is portable across SQLite and PostgreSQL:
--   * TRUE/FALSE booleans are understood by both.
--   * dimension keys are resolved by joining on natural keys.
--   * on-time is a lexicographic compare of ISO date strings (YYYY-MM-DD),
--     which equals a chronological compare - no engine-specific date maths.
-- Re-running is safe: the pipeline first deletes this partition's fact rows
-- (see transform.py), making the whole step idempotent.

-- name: insert_fact_for_partition
INSERT INTO fact_shipments
    (date_key, hub_key, status_key, price, freight_value, n_items,
     delivery_days, is_delivered, is_on_time)
SELECT
    d.date_key,
    h.hub_key,
    os.status_key,
    st.price,
    st.freight_value,
    st.n_items,
    st.delivery_days,
    CASE WHEN st.order_status = 'delivered' THEN TRUE ELSE FALSE END AS is_delivered,
    CASE
        WHEN st.order_status = 'delivered'
         AND st.delivered_date IS NOT NULL
         AND st.delivered_date <> ''
         AND st.delivered_date <= st.estimated_date
        THEN TRUE ELSE FALSE
    END AS is_on_time
FROM stg_shipments st
JOIN dim_date         d  ON d.date         = st.purchase_date
JOIN dim_hub          h  ON h.hub_code     = st.customer_state
JOIN dim_order_status os ON os.order_status = st.order_status
WHERE st.load_date = :load_date;
