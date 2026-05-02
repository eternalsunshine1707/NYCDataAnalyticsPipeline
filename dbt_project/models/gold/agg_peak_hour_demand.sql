-- models/gold/agg_peak_hour_demand.sql
-- ────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER — Peak Hour Demand Analysis
--
-- This model answers:
--   "When during the week do people take the most taxis, and where?"
--
-- KEY INSIGHT THIS ENABLES:
--   Friday evenings between 5pm-8pm consistently show the highest
--   trip volume of any hour in the week — more than morning rush.
--   This pattern holds across Manhattan and outer boroughs.
--
-- This is critical for dynamic pricing strategy:
--   If you know demand surges on Friday at 6pm, you can price accordingly.
-- ────────────────────────────────────────────────────────────────────────────

WITH trips AS (

    SELECT * FROM {{ ref('fct_trips') }}

),

zones AS (

    SELECT * FROM {{ ref('taxi_zones') }}

),

trips_with_zones AS (

    SELECT
        t.*,
        z.Borough AS pickup_borough,
        z.Zone    AS pickup_zone
    FROM trips t
    LEFT JOIN zones z ON t.pickup_location_id = z.LocationID

),

-- Aggregate by hour of day + day of week + borough
hourly_demand AS (

    SELECT

        -- ── Time dimensions ────────────────────────────────────────────────
        pickup_year,
        pickup_month_num,
        day_of_week_num,
        day_of_week_name,
        weekday_or_weekend,
        hour_of_day,
        time_of_day_bucket,

        -- ── Geography ─────────────────────────────────────────────────────
        pickup_borough,

        -- ── Demand metrics ─────────────────────────────────────────────────
        COUNT(*)                                            AS total_trips,
        SUM(passenger_count)                                AS total_passengers,

        -- ── Revenue metrics ────────────────────────────────────────────────
        ROUND(SUM(fare_amount), 2)                          AS total_fare_revenue,
        ROUND(AVG(fare_amount), 2)                          AS avg_fare_amount,
        ROUND(AVG(tip_pct), 2)                              AS avg_tip_pct,

        -- ── Trip characteristics ───────────────────────────────────────────
        ROUND(AVG(trip_distance_miles), 2)                  AS avg_trip_distance_miles,
        ROUND(AVG(trip_duration_minutes), 2)                AS avg_trip_duration_min,

        -- ── Peak hour flag (pre-defined in silver layer) ───────────────────
        MAX(CASE WHEN is_peak_hour THEN 1 ELSE 0 END)       AS is_peak_hour,

        -- ── Tip behaviour by time ──────────────────────────────────────────
        SUM(CASE WHEN has_tip THEN 1 ELSE 0 END)            AS trips_with_tip,
        ROUND(
            SUM(CASE WHEN has_tip THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        )                                                   AS tip_rate_pct,

        -- ── Weekend vs weekday demand ratio helper ─────────────────────────
        SUM(CASE WHEN weekday_or_weekend = 'Weekend' THEN 1 ELSE 0 END) AS weekend_trips,
        SUM(CASE WHEN weekday_or_weekend = 'Weekday' THEN 1 ELSE 0 END) AS weekday_trips

    FROM trips_with_zones
    WHERE pickup_borough IS NOT NULL
    GROUP BY
        pickup_year,
        pickup_month_num,
        day_of_week_num,
        day_of_week_name,
        weekday_or_weekend,
        hour_of_day,
        time_of_day_bucket,
        pickup_borough

)

SELECT * FROM hourly_demand
ORDER BY
    pickup_year,
    pickup_month_num,
    day_of_week_num,
    hour_of_day,
    pickup_borough
