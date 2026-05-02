"""
ingestion/ingest.py
-------------------
Downloads NYC Yellow Cab trip data from the NYC TLC public dataset
and uploads it to your AWS S3 bucket.

The NYC TLC (Taxi & Limousine Commission) publishes monthly Parquet files
at a public URL. Each file is ~100-300MB and covers one month of all
yellow cab trips in New York City.

Why Parquet? It's a compressed, column-oriented format — perfect for
analytics. A 300MB Parquet file would be ~2GB as a CSV.
"""

import os
import sys
import boto3
import requests
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential
import tempfile

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_RAW_PREFIX = os.getenv("S3_RAW_PREFIX", "raw/yellow_taxi/")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# ── Logger Setup ───────────────────────────────────────────────────────────────

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
    level="INFO",
)
logger.add("logs/ingestion.log", rotation="10 MB", retention="30 days", level="DEBUG")

os.makedirs("logs", exist_ok=True)


# ── Core Functions ─────────────────────────────────────────────────────────────


def build_url(year: int, month: int) -> str:
    """Build the public TLC download URL for a given year/month."""
    return f"{BASE_URL}/yellow_tripdata_{year}-{month:02d}.parquet"


def build_s3_key(year: int, month: int) -> str:
    """Build the S3 key (path inside the bucket) for a given year/month."""
    return f"{S3_RAW_PREFIX}year={year}/month={month:02d}/yellow_tripdata_{year}-{month:02d}.parquet"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def download_file(url: str, dest_path: Path) -> int:
    """
    Download a file from a URL with a progress bar and retry logic.
    Returns the file size in bytes.

    We use streaming so we never load the whole file into memory at once —
    each chunk is written to disk as it arrives.
    """
    logger.info(f"Downloading: {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    block_size = 8192  # 8KB chunks

    with open(dest_path, "wb") as f, tqdm(
        desc=dest_path.name,
        total=total_size,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(block_size):
            size = f.write(chunk)
            bar.update(size)

    return dest_path.stat().st_size


def file_exists_in_s3(s3_client, bucket: str, key: str) -> bool:
    """Check if a file already exists in S3 to avoid re-uploading."""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except s3_client.exceptions.ClientError:
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def upload_to_s3(s3_client, local_path: Path, bucket: str, key: str) -> None:
    """
    Upload a local file to S3 with a progress bar.
    We use multipart upload automatically for large files (boto3 handles this).
    """
    file_size = local_path.stat().st_size
    logger.info(f"Uploading to s3://{bucket}/{key} ({file_size / 1e6:.1f} MB)")

    with tqdm(total=file_size, unit="iB", unit_scale=True, desc="Uploading") as bar:
        s3_client.upload_file(
            str(local_path),
            bucket,
            key,
            Callback=lambda bytes_transferred: bar.update(bytes_transferred),
        )

    logger.success(f"Uploaded: s3://{bucket}/{key}")


def ingest_month(s3_client, year: int, month: int, skip_existing: bool = True) -> dict:
    """
    Full pipeline for one month:
      1. Check if already in S3
      2. Download from NYC TLC
      3. Upload to S3
      4. Delete local temp file

    Returns a dict summarising what happened.
    """
    url = build_url(year, month)
    s3_key = build_s3_key(year, month)
    label = f"{year}-{month:02d}"

    # Skip if already uploaded
    if skip_existing and file_exists_in_s3(s3_client, S3_BUCKET, s3_key):
        logger.info(f"[{label}] Already in S3, skipping.")
        return {"month": label, "status": "skipped", "bytes": 0}

    # Download to a temporary file so we clean up automatically
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / f"yellow_tripdata_{year}-{month:02d}.parquet"

        try:
            bytes_downloaded = download_file(url, local_path)
            upload_to_s3(s3_client, local_path, S3_BUCKET, s3_key)
            return {"month": label, "status": "success", "bytes": bytes_downloaded}

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"[{label}] Data not available yet (404). Skipping.")
                return {"month": label, "status": "not_available", "bytes": 0}
            raise


def run_ingestion(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    skip_existing: bool = True,
) -> None:
    """
    Main entry point — loops through every month in the date range
    and ingests each one.
    """
    if not S3_BUCKET:
        raise ValueError("S3_BUCKET_NAME not set in .env file.")

    logger.info(f"Starting ingestion: {start_year}-{start_month:02d} → {end_year}-{end_month:02d}")
    logger.info(f"Target bucket: s3://{S3_BUCKET}/{S3_RAW_PREFIX}")

    s3_client = boto3.client("s3", region_name=AWS_REGION)

    results = []

    # Build list of (year, month) tuples to process
    months_to_process = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months_to_process.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    logger.info(f"Processing {len(months_to_process)} month(s)...")

    for year, month in months_to_process:
        result = ingest_month(s3_client, year, month, skip_existing)
        results.append(result)

    # Summary
    success = [r for r in results if r["status"] == "success"]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] == "not_available"]

    total_bytes = sum(r["bytes"] for r in success)

    logger.info("─" * 50)
    logger.info(f"Ingestion complete!")
    logger.info(f"  ✅ Uploaded:  {len(success)} months")
    logger.info(f"  ⏭  Skipped:   {len(skipped)} months (already in S3)")
    logger.info(f"  ⚠️  Not found: {len(failed)} months")
    logger.info(f"  📦 Total data: {total_bytes / 1e9:.2f} GB")


# ── CLI Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import click

    @click.command()
    @click.option("--start-year", default=int(os.getenv("START_YEAR", 2023)), help="Start year")
    @click.option("--start-month", default=int(os.getenv("START_MONTH", 1)), help="Start month (1-12)")
    @click.option("--end-year", default=int(os.getenv("END_YEAR", 2023)), help="End year")
    @click.option("--end-month", default=int(os.getenv("END_MONTH", 12)), help="End month (1-12)")
    @click.option("--no-skip", is_flag=True, default=False, help="Re-upload even if already in S3")
    def main(start_year, start_month, end_year, end_month, no_skip):
        """Download NYC TLC yellow cab data and upload to S3."""
        run_ingestion(
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            skip_existing=not no_skip,
        )

    main()
