-- models/gold/agg_tip_behavior.sql
-- ────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER — Tip Behaviour Patterns
--
-- This model answers:
--   "Who tips, how much, and under what circumstances?"
--
-- Key things we look at:
--   • Does payment method affect tip amount? (Credit card vs cash)
--   • Do airport trips generate higher tips?
--   • What's the relationship between trip distance and tip percentage?
--   • Which boroughs tip the most?
--   • Does time of day affect tipping?
--
-- Why does this matter?
--   For drivers, understanding tipping patterns = understanding real earnings.
--   For platforms, it informs incentive design and driver compensation models.
-- ────────────────────────────────────────────────────────────────────────────

WITH trips AS (

    SELECT * FROM {{ ref('fct_trips') }}

),

zones AS (

    SELECT * FROM {{ ref('taxi_zones') }}

),

trips_enriched AS (

    SELECT
        t.*,
        z.Borough AS pickup_borough
    FROM trips t
    LEFT JOIN zones z ON t.pickup_location_id = z.LocationID

),

-- Tip analysis grouped by key behavioural dimensions
tip_analysis AS (

    SELECT

        -- ── Grouping dimensions ────────────────────────────────────────────
        pickup_borough,
        payment_type_name,
        time_of_day_bucket,
        weekday_or_weekend,
        is_airport_trip,
        pickup_year,
        pickup_month_num,

        -- ── Volume ─────────────────────────────────────────────────────────
        COUNT(*)                                            AS total_trips,

        -- ── Tip rate (% of trips that include a tip) ─────────────────────
        SUM(CASE WHEN has_tip THEN 1 ELSE 0 END)            AS trips_with_tip,
        ROUND(
            SUM(CASE WHEN has_tip THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        )                                                   AS tip_rate_pct,

        -- ── Tip amount stats ────────────────────────────────────────────────
        ROUND(AVG(tip_amount), 2)                           AS avg_tip_amount,
        ROUND(AVG(CASE WHEN has_tip THEN tip_amount END), 2) AS avg_tip_when_tipped,
        ROUND(AVG(tip_pct), 2)                              AS avg_tip_pct_of_fare,
        ROUND(SUM(tip_amount), 2)                           AS total_tip_revenue,

        -- ── Fare stats (for context) ────────────────────────────────────────
        ROUND(AVG(fare_amount), 2)                          AS avg_fare_amount,
        ROUND(AVG(trip_distance_miles), 2)                  AS avg_trip_distance_miles,
        ROUND(AVG(trip_duration_minutes), 2)                AS avg_trip_duration_min,

        -- ── Tip distribution ───────────────────────────────────────────────
        ROUND(APPROX_PERCENTILE(tip_amount, 0.50), 2)       AS median_tip_amount,
        ROUND(APPROX_PERCENTILE(tip_pct, 0.50), 2)          AS median_tip_pct,
        ROUND(APPROX_PERCENTILE(tip_pct, 0.75), 2)          AS p75_tip_pct,

        -- ── High tipper flag: ≥20% tip ─────────────────────────────────────
        SUM(CASE WHEN tip_pct >= 20 THEN 1 ELSE 0 END)      AS generous_tippers,
        ROUND(
            SUM(CASE WHEN tip_pct >= 20 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        )                                                   AS generous_tipper_pct

    FROM trips_enriched
    WHERE
        pickup_borough IS NOT NULL
        -- Only include credit card trips for tip analysis
        -- Cash tips aren't recorded in the data, which would skew averages
        AND payment_type = 1
    GROUP BY
        pickup_borough,
        payment_type_name,
        time_of_day_bucket,
        weekday_or_weekend,
        is_airport_trip,
        pickup_year,
        pickup_month_num

)

SELECT * FROM tip_analysis
ORDER BY pickup_borough, payment_type_name, weekday_or_weekend, time_of_day_bucket
