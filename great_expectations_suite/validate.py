"""
great_expectations_suite/validate.py
--------------------------------------
Data validation using Great Expectations.

Why validate? When you're ingesting 3M+ rows of real-world data,
things go wrong. Columns get renamed. Null values appear where they shouldn't.
Fare amounts become negative. Dates fall outside expected ranges.

This script checks the quality of the raw data BEFORE it flows into dbt.
If critical checks fail, the pipeline stops and alerts you — rather than
letting bad data silently poison your analytics.

We validate a sample of the data (the first Parquet file in S3) to keep
this fast. You can extend it to validate every file if needed.
"""

import os
import sys
import boto3
import pandas as pd
import awswrangler as wr
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_RAW_PREFIX = os.getenv("S3_RAW_PREFIX", "raw/yellow_taxi/")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "nyc_taxi_db")
ATHENA_OUTPUT = os.getenv("ATHENA_OUTPUT_LOCATION")


# ── Expectation Definitions ────────────────────────────────────────────────────
#
# Each expectation is a function that takes a DataFrame and returns
# (passed: bool, message: str). This keeps things simple and readable.


def expect_columns_exist(df: pd.DataFrame, required_cols: list) -> tuple:
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return False, f"Missing columns: {missing}"
    return True, f"All {len(required_cols)} required columns present"


def expect_no_nulls(df: pd.DataFrame, col: str) -> tuple:
    null_count = df[col].isnull().sum()
    pct = null_count / len(df) * 100
    if null_count > 0:
        return False, f"Column '{col}' has {null_count:,} nulls ({pct:.1f}%)"
    return True, f"Column '{col}' has 0 nulls ✓"


def expect_values_in_range(df: pd.DataFrame, col: str, min_val, max_val) -> tuple:
    out_of_range = df[(df[col] < min_val) | (df[col] > max_val)][col]
    pct = len(out_of_range) / len(df) * 100
    if len(out_of_range) > 0:
        # Allow up to 1% bad rows — real-world data is messy
        if pct > 1.0:
            return False, f"Column '{col}': {len(out_of_range):,} values ({pct:.1f}%) outside [{min_val}, {max_val}]"
    return True, f"Column '{col}' values mostly within [{min_val}, {max_val}] ({pct:.2f}% outliers)"


def expect_row_count(df: pd.DataFrame, min_rows: int) -> tuple:
    if len(df) < min_rows:
        return False, f"Only {len(df):,} rows — expected at least {min_rows:,}"
    return True, f"Row count: {len(df):,} ✓"


def expect_date_range(df: pd.DataFrame, col: str, start: str, end: str) -> tuple:
    try:
        dates = pd.to_datetime(df[col], errors="coerce")
        out_of_range = dates[(dates < start) | (dates > end)]
        pct = len(out_of_range) / len(df) * 100
        if pct > 2.0:
            return False, f"Column '{col}': {pct:.1f}% dates outside [{start}, {end}]"
        return True, f"Column '{col}' dates mostly in range ({pct:.2f}% outliers)"
    except Exception as e:
        return False, f"Date check failed for '{col}': {e}"


def expect_no_duplicate_trip_ids(df: pd.DataFrame) -> tuple:
    """
    NYC TLC data doesn't have a true trip ID, but we can check for
    exact duplicate rows — same pickup time, dropoff, passenger count, fare.
    """
    key_cols = ["tpep_pickup_datetime", "tpep_dropoff_datetime", "fare_amount", "PULocationID", "DOLocationID"]
    available = [c for c in key_cols if c in df.columns]
    dupe_count = df.duplicated(subset=available).sum()
    pct = dupe_count / len(df) * 100
    if pct > 0.5:
        return False, f"{dupe_count:,} duplicate rows ({pct:.2f}%) — investigate!"
    return True, f"Duplicate rows: {dupe_count:,} ({pct:.2f}%) — acceptable ✓"


# ── Main Validation Runner ─────────────────────────────────────────────────────


def run_validation(sample_s3_path: str = None) -> bool:
    """
    Load a sample of the raw data and run all expectations.
    Returns True if all critical checks pass.
    """
    logger.info("Starting data validation...")

    # Find the first Parquet file in S3 if no path provided
    if not sample_s3_path:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_RAW_PREFIX, MaxKeys=5)
        parquet_files = [
            f"s3://{S3_BUCKET}/{obj['Key']}"
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".parquet")
        ]
        if not parquet_files:
            logger.error("No Parquet files found in S3. Run ingestion first.")
            return False
        sample_s3_path = parquet_files[0]

    logger.info(f"Validating: {sample_s3_path}")

    # Load sample (first 100K rows for speed)
    try:
        df = wr.s3.read_parquet(path=sample_s3_path, boto3_session=boto3.Session(region_name=AWS_REGION))
        logger.info(f"Loaded {len(df):,} rows for validation")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return False

    # ── Define expectations ────────────────────────────────────────────────────

    REQUIRED_COLUMNS = [
        "tpep_pickup_datetime",
        "tpep_dropoff_datetime",
        "passenger_count",
        "trip_distance",
        "PULocationID",
        "DOLocationID",
        "fare_amount",
        "tip_amount",
        "total_amount",
        "payment_type",
    ]

    expectations = [
        expect_row_count(df, min_rows=100_000),
        expect_columns_exist(df, REQUIRED_COLUMNS),
        expect_no_nulls(df, "tpep_pickup_datetime"),
        expect_no_nulls(df, "tpep_dropoff_datetime"),
        expect_no_nulls(df, "fare_amount"),
        expect_values_in_range(df, "fare_amount", min_val=0.0, max_val=1000.0),
        expect_values_in_range(df, "trip_distance", min_val=0.0, max_val=200.0),
        expect_values_in_range(df, "passenger_count", min_val=0, max_val=9),
        expect_values_in_range(df, "tip_amount", min_val=0.0, max_val=500.0),
        expect_no_duplicate_trip_ids(df),
    ]

    # ── Run and report ─────────────────────────────────────────────────────────

    logger.info("\n" + "─" * 60)
    logger.info("VALIDATION RESULTS")
    logger.info("─" * 60)

    passed = 0
    failed = 0
    failed_critical = []

    for success, message in expectations:
        if success:
            logger.info(f"  ✅ PASS — {message}")
            passed += 1
        else:
            logger.warning(f"  ❌ FAIL — {message}")
            failed += 1
            failed_critical.append(message)

    logger.info("─" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed")

    if failed_critical:
        logger.error("Critical checks failed. Review data quality before proceeding.")
        for msg in failed_critical:
            logger.error(f"  → {msg}")
        return False

    logger.success("All validations passed! Data is ready for dbt transformation.")
    return True


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
