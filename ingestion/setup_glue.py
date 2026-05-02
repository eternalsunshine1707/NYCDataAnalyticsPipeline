"""
ingestion/setup_glue.py
-----------------------
Sets up AWS Glue resources so that Athena can query your S3 data.

Here's the problem this solves:
  - Your raw data lives in S3 as Parquet files.
  - Athena is a query engine, but it needs a "catalogue" to know:
      * Where the files are
      * What columns exist
      * What data types each column has
  - AWS Glue maintains this catalogue.
  - A Glue "Crawler" scans your S3 bucket and auto-populates the catalogue.

This script:
  1. Creates a Glue database (like a namespace / folder for tables)
  2. Creates a Glue Crawler pointed at your S3 raw data
  3. Runs the Crawler and waits for it to finish
  4. Verifies the table was created and prints column info
"""

import os
import time
import boto3
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_RAW_PREFIX = os.getenv("S3_RAW_PREFIX", "raw/yellow_taxi/")
GLUE_DATABASE = os.getenv("GLUE_DATABASE", "nyc_taxi_db")
GLUE_CRAWLER_NAME = "nyc-taxi-raw-crawler"
GLUE_IAM_ROLE = os.getenv("GLUE_IAM_ROLE")  # Must be set — see README


def create_glue_database(glue_client) -> None:
    """Create the Glue database if it doesn't exist."""
    try:
        glue_client.create_database(
            DatabaseInput={
                "Name": GLUE_DATABASE,
                "Description": "NYC Taxi Trip Analytics — raw and processed data",
            }
        )
        logger.success(f"Created Glue database: {GLUE_DATABASE}")
    except glue_client.exceptions.AlreadyExistsException:
        logger.info(f"Glue database already exists: {GLUE_DATABASE}")


def create_glue_crawler(glue_client) -> None:
    """
    Create a Glue Crawler that scans s3://<bucket>/raw/yellow_taxi/
    and registers the schema in the Glue catalogue.
    """
    s3_target = f"s3://{S3_BUCKET}/{S3_RAW_PREFIX}"

    try:
        glue_client.create_crawler(
            Name=GLUE_CRAWLER_NAME,
            Role=GLUE_IAM_ROLE,
            DatabaseName=GLUE_DATABASE,
            Description="Crawls raw NYC TLC yellow cab Parquet files",
            Targets={
                "S3Targets": [
                    {
                        "Path": s3_target,
                        # Use Hive-style partitioning (year=XXXX/month=XX)
                        # so Athena can filter by partition and skip reading irrelevant files
                        "Exclusions": [],
                    }
                ]
            },
            SchemaChangePolicy={
                "UpdateBehavior": "UPDATE_IN_DATABASE",
                "DeleteBehavior": "LOG",
            },
            Configuration='{"Version":1.0,"CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"}}}',
        )
        logger.success(f"Created Glue Crawler: {GLUE_CRAWLER_NAME}")
    except glue_client.exceptions.AlreadyExistsException:
        logger.info(f"Glue Crawler already exists: {GLUE_CRAWLER_NAME}")


def run_crawler_and_wait(glue_client, timeout_minutes: int = 30) -> None:
    """
    Trigger the crawler and poll until it finishes.
    Crawling 3M+ rows of Parquet typically takes 3-8 minutes.
    """
    logger.info(f"Starting crawler: {GLUE_CRAWLER_NAME}")
    glue_client.start_crawler(Name=GLUE_CRAWLER_NAME)

    timeout_seconds = timeout_minutes * 60
    poll_interval = 15
    elapsed = 0

    while elapsed < timeout_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval

        response = glue_client.get_crawler(Name=GLUE_CRAWLER_NAME)
        state = response["Crawler"]["State"]
        logger.info(f"Crawler state: {state} (elapsed: {elapsed}s)")

        if state == "READY":
            last_crawl = response["Crawler"].get("LastCrawl", {})
            status = last_crawl.get("Status", "UNKNOWN")
            if status == "SUCCEEDED":
                logger.success("Crawler finished successfully!")
                return
            else:
                raise RuntimeError(f"Crawler finished with status: {status}")

    raise TimeoutError(f"Crawler did not finish within {timeout_minutes} minutes.")


def verify_table(glue_client) -> None:
    """Print the table schema that the crawler discovered."""
    try:
        tables = glue_client.get_tables(DatabaseName=GLUE_DATABASE)["TableList"]
        logger.info(f"Tables in {GLUE_DATABASE}:")
        for table in tables:
            logger.info(f"  📋 {table['Name']}")
            cols = table["StorageDescriptor"]["Columns"]
            logger.info(f"     Columns ({len(cols)}):")
            for col in cols[:10]:  # show first 10
                logger.info(f"       • {col['Name']} ({col['Type']})")
            if len(cols) > 10:
                logger.info(f"       ... and {len(cols) - 10} more")
    except Exception as e:
        logger.warning(f"Could not verify table: {e}")


def setup_glue() -> None:
    """Run the full Glue setup."""
    if not S3_BUCKET:
        raise ValueError("S3_BUCKET_NAME not set in .env")
    if not GLUE_IAM_ROLE:
        raise ValueError(
            "GLUE_IAM_ROLE not set in .env. "
            "Create an IAM role with AWSGlueServiceRole + S3 read access. "
            "See docs/aws_setup.md for instructions."
        )

    logger.info("Setting up AWS Glue resources...")
    glue_client = boto3.client("glue", region_name=AWS_REGION)

    create_glue_database(glue_client)
    create_glue_crawler(glue_client)
    run_crawler_and_wait(glue_client)
    verify_table(glue_client)

    logger.success("Glue setup complete! You can now run dbt models.")


if __name__ == "__main__":
    setup_glue()
