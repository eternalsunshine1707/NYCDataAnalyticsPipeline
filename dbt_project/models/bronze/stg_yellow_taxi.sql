-- models/bronze/stg_yellow_taxi.sql
-- ────────────────────────────────────────────────────────────────────────────
-- BRONZE LAYER — Raw staging model
--
-- This is just a thin wrapper over the raw source table.
-- We do MINIMAL transformation here — only enough to make
-- downstream models not crash on edge cases.
--
-- Think of this as "plug the raw S3 data into dbt".
-- ────────────────────────────────────────────────────────────────────────────

WITH raw AS (

    SELECT *
    FROM {{ source('raw', 'yellow_taxi') }}

    -- Optional dev filter: uncomment to limit rows during development
    -- WHERE year = '2023' AND month = '01'

)

SELECT

    -- ── Trip identifiers ────────────────────────────────────────────────────
    VendorID                                            AS vendor_id,

    -- ── Timestamps ──────────────────────────────────────────────────────────
    CAST(tpep_pickup_datetime  AS TIMESTAMP)            AS pickup_datetime,
    CAST(tpep_dropoff_datetime AS TIMESTAMP)            AS dropoff_datetime,

    -- ── Geography ───────────────────────────────────────────────────────────
    CAST(PULocationID AS INTEGER)                       AS pickup_location_id,
    CAST(DOLocationID AS INTEGER)                       AS dropoff_location_id,
    CAST(RatecodeID   AS INTEGER)                       AS rate_code_id,

    -- ── Trip details ─────────────────────────────────────────────────────────
    CAST(passenger_count AS INTEGER)                    AS passenger_count,
    CAST(trip_distance   AS DOUBLE)                     AS trip_distance_miles,
    store_and_fwd_flag,
    CAST(payment_type AS INTEGER)                       AS payment_type,

    -- ── Fare components ──────────────────────────────────────────────────────
    CAST(fare_amount            AS DOUBLE)              AS fare_amount,
    CAST(COALESCE(extra, 0)     AS DOUBLE)              AS extra_amount,
    CAST(COALESCE(mta_tax, 0)   AS DOUBLE)              AS mta_tax,
    CAST(tip_amount             AS DOUBLE)              AS tip_amount,
    CAST(COALESCE(tolls_amount, 0)           AS DOUBLE) AS tolls_amount,
    CAST(COALESCE(improvement_surcharge, 0)  AS DOUBLE) AS improvement_surcharge,
    CAST(total_amount           AS DOUBLE)              AS total_amount,
    CAST(COALESCE(congestion_surcharge, 0)   AS DOUBLE) AS congestion_surcharge,
    CAST(COALESCE(airport_fee, 0)            AS DOUBLE) AS airport_fee,

    -- ── Partitioning columns (added by Glue crawler) ──────────────────────
    year,
    month

FROM raw
