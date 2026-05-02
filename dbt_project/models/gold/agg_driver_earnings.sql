-- models/gold/agg_driver_earnings.sql
-- ────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER — Driver Earnings Distribution
--
-- This model looks at earnings from the driver's perspective.
-- A driver's gross take includes: fare + tip + extras (but NOT tolls,
-- taxes, and platform fees which go elsewhere).
--
-- We aggregate this by borough and time period to show:
--   • Which pickup zones generate the best earnings per hour?
--   • What does an "average shift" look like in different boroughs?
--   • How does earnings/trip vary across time of day?
--
-- Why is this useful?
--   Drivers make strategic decisions about WHERE to work and WHEN.
--   This data helps surface those trade-offs clearly.
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
        -- Driver's gross earnings per trip (excludes MTA tax, tolls, improvement surcharge)
        ROUND(t.fare_amount + t.tip_amount + t.extra_amount + t.congestion_surcharge, 2) AS driver_gross_earn,

        -- Earnings per minute of trip (proxy for hourly rate)
        ROUND(
            (t.fare_amount + t.tip_amount + t.extra_amount) /
            NULLIF(t.trip_duration_minutes, 0),
            4
        ) AS earn_per_minute,

        z.Borough AS pickup_borough,
        z.Zone    AS pickup_zone

    FROM trips t
    LEFT JOIN zones z ON t.pickup_location_id = z.LocationID

),

earnings_by_borough_time AS (

    SELECT

        -- ── Grouping dimensions ────────────────────────────────────────────
        pickup_borough,
        pickup_year,
        pickup_month_num,
        day_of_week_name,
        weekday_or_weekend,
        time_of_day_bucket,
        hour_of_day,

        -- ── Volume ─────────────────────────────────────────────────────────
        COUNT(*)                                            AS total_trips,

        -- ── Earnings per trip ──────────────────────────────────────────────
        ROUND(AVG(driver_gross_earn), 2)                    AS avg_earnings_per_trip,
        ROUND(SUM(driver_gross_earn), 2)                    AS total_earnings,
        ROUND(MIN(driver_gross_earn), 2)                    AS min_earnings_per_trip,
        ROUND(MAX(driver_gross_earn), 2)                    AS max_earnings_per_trip,
        ROUND(APPROX_PERCENTILE(driver_gross_earn, 0.50), 2) AS median_earnings_per_trip,
        ROUND(APPROX_PERCENTILE(driver_gross_earn, 0.75), 2) AS p75_earnings_per_trip,

        -- ── Earnings per minute ────────────────────────────────────────────
        ROUND(AVG(earn_per_minute) * 60, 2)                 AS avg_implied_hourly_rate,

        -- ── Trip characteristics ────────────────────────────────────────────
        ROUND(AVG(trip_distance_miles), 2)                  AS avg_trip_distance_miles,
        ROUND(AVG(trip_duration_minutes), 2)                AS avg_trip_duration_min,
        ROUND(AVG(fare_amount), 2)                          AS avg_base_fare,
        ROUND(AVG(tip_amount), 2)                           AS avg_tip,
        ROUND(AVG(tip_pct), 2)                              AS avg_tip_pct,

        -- ── High-value trip count (>$25 gross) ────────────────────────────
        SUM(CASE WHEN driver_gross_earn > 25 THEN 1 ELSE 0 END) AS high_value_trips,
        ROUND(
            SUM(CASE WHEN driver_gross_earn > 25 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        )                                                   AS high_value_trip_pct

    FROM trips_enriched
    WHERE pickup_borough IS NOT NULL
    GROUP BY
        pickup_borough,
        pickup_year,
        pickup_month_num,
        day_of_week_name,
        weekday_or_weekend,
        time_of_day_bucket,
        hour_of_day

)

SELECT * FROM earnings_by_borough_time
ORDER BY pickup_borough, pickup_year, pickup_month_num, hour_of_day
