-- models/silver/fct_trips.sql
-- ────────────────────────────────────────────────────────────────────────────
-- SILVER LAYER — Clean, validated trip facts
--
-- This is where the heavy lifting happens.
-- We take the raw bronze data and:
--   1. Remove bad rows (impossible fares, negative distances, etc.)
--   2. Add calculated columns (trip duration, tip percentage, etc.)
--   3. Label coded values (payment_type 1 → "Credit Card")
--   4. Add time breakdowns (hour of day, day of week, etc.)
--   5. Join with the taxi zone lookup table for borough names
--
-- After this model runs, every row represents ONE valid NYC taxi trip.
-- ────────────────────────────────────────────────────────────────────────────

WITH bronze AS (

    SELECT * FROM {{ ref('stg_yellow_taxi') }}

),

-- ── Step 1: Filter out invalid/impossible trips ────────────────────────────
--
-- Real-world data contains garbage. These filters remove rows that are
-- clearly wrong — not just messy, but logically impossible.

cleaned AS (

    SELECT *
    FROM bronze
    WHERE
        -- Trip must have valid timestamps
        pickup_datetime  IS NOT NULL
        AND dropoff_datetime IS NOT NULL

        -- Dropoff must be after pickup
        AND dropoff_datetime > pickup_datetime

        -- Trip duration must be between 1 minute and 6 hours
        AND DATE_DIFF('minute', pickup_datetime, dropoff_datetime) BETWEEN 1 AND 360

        -- Fare must be positive (negative fares = refunds/errors, $0 = not a real trip)
        AND fare_amount > 0
        AND fare_amount < 1000  -- protect against data entry errors

        -- Distance must be positive
        AND trip_distance_miles > 0
        AND trip_distance_miles < 200  -- longest possible NYC taxi trip

        -- Location IDs must be valid NYC zones (1-265)
        AND pickup_location_id  BETWEEN 1 AND {{ var('max_location_id') }}
        AND dropoff_location_id BETWEEN 1 AND {{ var('max_location_id') }}

        -- Passenger count must be valid
        AND passenger_count BETWEEN 1 AND 8

        -- Tip can't be negative
        AND tip_amount >= 0

        -- Only include data within the configured date range
        AND pickup_datetime >= CAST('{{ var("start_date") }}' AS TIMESTAMP)
        AND pickup_datetime <  CAST('{{ var("end_date") }}'   AS TIMESTAMP)

),

-- ── Step 2: Enrich with calculated fields ─────────────────────────────────

enriched AS (

    SELECT

        -- ── Original fields ────────────────────────────────────────────────
        *,

        -- ── Trip duration ──────────────────────────────────────────────────
        DATE_DIFF('minute', pickup_datetime, dropoff_datetime)  AS trip_duration_minutes,
        DATE_DIFF('second', pickup_datetime, dropoff_datetime)  AS trip_duration_seconds,

        -- ── Speed (approximate — straight-line distance not actual route) ──
        ROUND(
            trip_distance_miles /
            NULLIF(DATE_DIFF('minute', pickup_datetime, dropoff_datetime) / 60.0, 0),
            2
        )                                                        AS avg_speed_mph,

        -- ── Fare per mile ──────────────────────────────────────────────────
        ROUND(fare_amount / NULLIF(trip_distance_miles, 0), 2)  AS fare_per_mile,

        -- ── Tip percentage (of base fare) ─────────────────────────────────
        ROUND(tip_amount / NULLIF(fare_amount, 0) * 100, 2)     AS tip_pct,

        -- ── Time breakdown ─────────────────────────────────────────────────
        CAST(DATE_TRUNC('day',  pickup_datetime) AS DATE)        AS pickup_date,
        CAST(DATE_TRUNC('hour', pickup_datetime) AS TIMESTAMP)   AS pickup_hour,
        HOUR(pickup_datetime)                                    AS hour_of_day,
        DAY_OF_WEEK(pickup_datetime)                             AS day_of_week_num,  -- 1=Sun, 7=Sat

        CASE DAY_OF_WEEK(pickup_datetime)
            WHEN 1 THEN 'Sunday'
            WHEN 2 THEN 'Monday'
            WHEN 3 THEN 'Tuesday'
            WHEN 4 THEN 'Wednesday'
            WHEN 5 THEN 'Thursday'
            WHEN 6 THEN 'Friday'
            WHEN 7 THEN 'Saturday'
        END                                                      AS day_of_week_name,

        CASE
            WHEN DAY_OF_WEEK(pickup_datetime) IN (1, 7) THEN 'Weekend'
            ELSE 'Weekday'
        END                                                      AS weekday_or_weekend,

        -- ── Time of day bucket ─────────────────────────────────────────────
        CASE
            WHEN HOUR(pickup_datetime) BETWEEN  0 AND  5 THEN 'Late Night (12am-6am)'
            WHEN HOUR(pickup_datetime) BETWEEN  6 AND  9 THEN 'Morning Rush (6am-10am)'
            WHEN HOUR(pickup_datetime) BETWEEN 10 AND 11 THEN 'Mid Morning (10am-12pm)'
            WHEN HOUR(pickup_datetime) BETWEEN 12 AND 13 THEN 'Lunch (12pm-2pm)'
            WHEN HOUR(pickup_datetime) BETWEEN 14 AND 16 THEN 'Afternoon (2pm-5pm)'
            WHEN HOUR(pickup_datetime) BETWEEN 17 AND 19 THEN 'Evening Rush (5pm-8pm)'
            WHEN HOUR(pickup_datetime) BETWEEN 20 AND 22 THEN 'Evening (8pm-11pm)'
            ELSE                                               'Late Night (11pm-12am)'
        END                                                      AS time_of_day_bucket,

        -- ── Month ──────────────────────────────────────────────────────────
        MONTH(pickup_datetime)                                   AS pickup_month_num,
        YEAR(pickup_datetime)                                    AS pickup_year,

        -- ── Rate code label ────────────────────────────────────────────────
        CASE rate_code_id
            WHEN 1 THEN 'Standard Rate'
            WHEN 2 THEN 'JFK Airport'
            WHEN 3 THEN 'Newark Airport'
            WHEN 4 THEN 'Nassau/Westchester'
            WHEN 5 THEN 'Negotiated Fare'
            WHEN 6 THEN 'Group Ride'
            ELSE        'Unknown'
        END                                                      AS rate_code_name,

        -- ── Payment type label ─────────────────────────────────────────────
        CASE payment_type
            WHEN 1 THEN 'Credit Card'
            WHEN 2 THEN 'Cash'
            WHEN 3 THEN 'No Charge'
            WHEN 4 THEN 'Dispute'
            WHEN 5 THEN 'Unknown'
            WHEN 6 THEN 'Voided'
            ELSE        'Unknown'
        END                                                      AS payment_type_name,

        -- ── Tip flag ──────────────────────────────────────────────────────
        CASE WHEN tip_amount > 0 THEN TRUE ELSE FALSE END        AS has_tip,

        -- ── Airport flag ──────────────────────────────────────────────────
        CASE WHEN rate_code_id IN (2, 3) THEN TRUE ELSE FALSE END AS is_airport_trip,

        -- ── Peak hour flag (morning + evening rush) ────────────────────────
        CASE
            WHEN HOUR(pickup_datetime) BETWEEN 7 AND 9  THEN TRUE  -- morning rush
            WHEN HOUR(pickup_datetime) BETWEEN 17 AND 19 THEN TRUE -- evening rush
            ELSE FALSE
        END                                                      AS is_peak_hour

    FROM cleaned

)

SELECT * FROM enriched
