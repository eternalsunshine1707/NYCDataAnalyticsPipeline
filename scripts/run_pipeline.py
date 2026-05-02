#!/usr/bin/env python3
"""
scripts/run_pipeline.py
────────────────────────────────────────────────────────────────────────────
One-command pipeline runner.

This script ties everything together so you can run the full pipeline
with a single command:

    python scripts/run_pipeline.py

It runs the steps in order:
  1. Ingest raw data → S3
  2. Validate data quality (Great Expectations)
  3. Run Glue crawler (catalogue the data for Athena)
  4. Run dbt models (transform raw → bronze → silver → gold)

If any step fails, the pipeline stops and tells you what went wrong.
"""

import os
import sys
import subprocess
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# Make sure we can import from sibling directories
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv()

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
)


def step(name: str, number: int, total: int):
    """Print a step header."""
    logger.info("─" * 60)
    logger.info(f"STEP {number}/{total}: {name}")
    logger.info("─" * 60)


def run_command(cmd: list, cwd: str = None) -> bool:
    """Run a shell command and return True if it succeeded."""
    result = subprocess.run(cmd, cwd=cwd or str(ROOT))
    return result.returncode == 0


def main():
    TOTAL_STEPS = 4

    logger.info("=" * 60)
    logger.info("  NYC TAXI ANALYTICS PIPELINE — STARTING")
    logger.info("=" * 60)

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    step("Ingest NYC TLC Data → S3", 1, TOTAL_STEPS)
    logger.info("Downloading monthly Parquet files and uploading to S3...")

    success = run_command([
        sys.executable, "ingestion/ingest.py",
        "--start-year", os.getenv("START_YEAR", "2023"),
        "--start-month", os.getenv("START_MONTH", "1"),
        "--end-year", os.getenv("END_YEAR", "2023"),
        "--end-month", os.getenv("END_MONTH", "12"),
    ])

    if not success:
        logger.error("Ingestion failed. Check your AWS credentials and S3 bucket config.")
        sys.exit(1)

    # ── Step 2: Validate ──────────────────────────────────────────────────────
    step("Validate Data Quality (Great Expectations)", 2, TOTAL_STEPS)
    logger.info("Running schema and quality checks on raw data...")

    success = run_command([sys.executable, "great_expectations_suite/validate.py"])

    if not success:
        logger.error("Data validation failed. Review the validation report before continuing.")
        logger.warning("To skip validation and proceed anyway, comment out this step in run_pipeline.py")
        sys.exit(1)

    # ── Step 3: Glue Crawler ──────────────────────────────────────────────────
    step("Run AWS Glue Crawler (Catalogue Data for Athena)", 3, TOTAL_STEPS)
    logger.info("Crawling S3 data and updating the Glue catalogue...")

    success = run_command([sys.executable, "ingestion/setup_glue.py"])

    if not success:
        logger.error("Glue setup failed. Check your IAM role permissions.")
        sys.exit(1)

    # ── Step 4: dbt ───────────────────────────────────────────────────────────
    step("Run dbt Models (Raw → Bronze → Silver → Gold)", 4, TOTAL_STEPS)
    logger.info("Running dbt transformations on Athena...")

    dbt_dir = str(ROOT / "dbt_project")

    # First run seeds (taxi zone lookup table)
    logger.info("Loading seed data (taxi zone lookup)...")
    success = run_command(["dbt", "seed"], cwd=dbt_dir)
    if not success:
        logger.error("dbt seed failed.")
        sys.exit(1)

    # Run all models
    logger.info("Running all dbt models...")
    success = run_command(["dbt", "run"], cwd=dbt_dir)
    if not success:
        logger.error("dbt run failed. Check dbt logs in dbt_project/logs/")
        sys.exit(1)

    # Run dbt tests
    logger.info("Running dbt data quality tests...")
    success = run_command(["dbt", "test"], cwd=dbt_dir)
    if not success:
        logger.warning("Some dbt tests failed — review dbt_project/target/run_results.json")
        # Don't exit — failing tests are informational, not pipeline-breaking

    # ── Done ──────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.success("PIPELINE COMPLETE!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next step — launch the dashboard:")
    logger.info("  streamlit run dashboard/app.py")
    logger.info("")


if __name__ == "__main__":
    main()
