-- models/gold/agg_fare_analytics.sql
-- ────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER — Fare Analytics by Borough and Zone
--
-- This model answers the question:
--   "What does a typical fare look like, broken down by where trips start?"
--
-- It powers the "Revenue & Fare Breakdown" section of the dashboard.
--
-- KEY INSIGHT THIS ENABLES:
--   Zones near airports, Manhattan midtown, and certain outer borough
--   corridors tend to generate significantly higher average fares —
--   both because of longer trips and rate code differences.
-- ────────────────────────────────────────────────────────────────────────────

WITH trips AS (

    SELECT * FROM {{ ref('fct_trips') }}

),

zones AS (

    SELECT * FROM {{ ref('taxi_zones') }}

),

-- Join trips with zone info so we know which borough each pickup was in
trips_with_zones AS (

    SELECT
        t.*,
        z.Borough    AS pickup_borough,
        z.Zone       AS pickup_zone,
        z.service_zone
    FROM trips t
    LEFT JOIN zones z
        ON t.pickup_location_id = z.LocationID

),

-- Aggregate fare metrics by borough and zone
aggregated AS (

    SELECT

        -- ── Grouping dimensions ────────────────────────────────────────────
        pickup_borough,
        pickup_zone,
        service_zone,
        pickup_year,
        pickup_month_num,
        payment_type_name,

        -- ── Volume metrics ─────────────────────────────────────────────────
        COUNT(*)                                        AS total_trips,
        SUM(passenger_count)                            AS total_passengers,

        -- ── Revenue metrics ────────────────────────────────────────────────
        ROUND(SUM(fare_amount), 2)                      AS total_fare_revenue,
        ROUND(SUM(tip_amount), 2)                       AS total_tip_revenue,
        ROUND(SUM(total_amount), 2)                     AS total_gross_revenue,

        -- ── Average fare metrics ───────────────────────────────────────────
        ROUND(AVG(fare_amount), 2)                      AS avg_fare_amount,
        ROUND(AVG(tip_amount), 2)                       AS avg_tip_amount,
        ROUND(AVG(total_amount), 2)                     AS avg_total_amount,
        ROUND(AVG(tip_pct), 2)                          AS avg_tip_pct,

        -- ── Distance & duration metrics ───────────────────────────────────
        ROUND(AVG(trip_distance_miles), 2)              AS avg_trip_distance_miles,
        ROUND(AVG(trip_duration_minutes), 2)            AS avg_trip_duration_min,
        ROUND(AVG(fare_per_mile), 2)                    AS avg_fare_per_mile,

        -- ── Percentile fare distribution (P25, P50, P75) ──────────────────
        ROUND(APPROX_PERCENTILE(fare_amount, 0.25), 2)  AS p25_fare,
        ROUND(APPROX_PERCENTILE(fare_amount, 0.50), 2)  AS p50_fare_median,
        ROUND(APPROX_PERCENTILE(fare_amount, 0.75), 2)  AS p75_fare,
        ROUND(APPROX_PERCENTILE(fare_amount, 0.90), 2)  AS p90_fare,

        -- ── Airport trip metrics ────────────────────────────────────────────
        SUM(CASE WHEN is_airport_trip THEN 1 ELSE 0 END) AS airport_trips,
        ROUND(
            SUM(CASE WHEN is_airport_trip THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        )                                               AS airport_trip_pct,

        -- ── Credit card vs cash breakdown ─────────────────────────────────
        SUM(CASE WHEN payment_type = 1 THEN 1 ELSE 0 END) AS credit_card_trips,
        SUM(CASE WHEN payment_type = 2 THEN 1 ELSE 0 END) AS cash_trips

    FROM trips_with_zones
    WHERE pickup_borough IS NOT NULL
    GROUP BY
        pickup_borough,
        pickup_zone,
        service_zone,
        pickup_year,
        pickup_month_num,
        payment_type_name

)

SELECT * FROM aggregated
ORDER BY pickup_borough, pickup_zone, pickup_year, pickup_month_num
