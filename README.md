# <ins>NYC Taxi Trip Analytics Pipeline</ins>

A complete data engineering project that ingests, cleans, transforms, and visualises over 3 million real New York City yellow cab trips - built on AWS, dbt, and Streamlit.

---

## What This Project Does

It takes raw, messy taxi trip data published by the NYC Taxi and Limousine Commission and turns it into a clean, interactive dashboard that answers real questions:

- When does demand surge during the week?
- Which boroughs generate higher fares?
- How do tipping patterns change by time of day?
- What does a driver actually earn per hour across different boroughs?

The data covers January 2024 through March 2026 - over two years of real trips.

---

## How Data Flows Through the System

```
NYC TLC Website (public Parquet files)
        |
        |  Python downloads monthly files and uploads to S3
        v
AWS S3 (raw data storage)
        |
        |  Great Expectations checks data quality
        |  AWS Glue Crawler scans files and registers the schema
        v
AWS Athena (SQL query engine over S3)
        |
        |  dbt runs transformations in 3 layers:
        |    Bronze  -->  Silver  -->  Gold
        v
Streamlit Dashboard
        |
        v
Interactive charts in your browser
```

---

## Why Each Tool Is Used

**Python** handles downloading the monthly Parquet files from the NYC TLC website and uploading them to S3. It also runs the data quality checks.

**AWS S3** is where all the raw files live. Think of it as a cloud hard drive. Everything else reads from here.

**Great Expectations** runs automated checks on the raw data before it flows into dbt. Things like - are fares always positive? Are location IDs valid? Are there duplicate rows? If something critical fails, the pipeline stops rather than letting bad data through.

**AWS Glue Crawler** scans the S3 files and registers the schema in a catalogue. This is what makes the data queryable through Athena - without it, Athena wouldn't know what columns exist or what types they are.

**AWS Athena** is a serverless query engine. You write SQL, it reads from S3 and gives you results back. No database server to maintain, and you only pay per query.

**dbt** runs the SQL transformations in three layers:

- Bronze - a thin wrapper over the raw source. Minimal changes, just type casting and column renaming.
- Silver - the real cleaning happens here. Bad rows removed, calculated fields added, coded values decoded into readable labels, time breakdowns added.
- Gold - pre-aggregated tables designed to answer specific questions fast. These are what the dashboard queries.

**Streamlit and Plotly** power the dashboard. It's all Python - no JavaScript needed.

---

## Project Structure

```
nyc-taxi-analytics/
|
|-- ingestion/
|   |-- ingest.py           downloads NYC TLC data and uploads to S3
|   |-- setup_glue.py       creates Glue database and crawler
|
|-- great_expectations_suite/
|   |-- validate.py         data quality checks
|
|-- dbt_project/
|   |-- dbt_project.yml     dbt configuration
|   |-- profiles_example.yml  copy this to ~/.dbt/profiles.yml
|   |-- seeds/
|   |   |-- taxi_zones.csv  NYC taxi zone lookup table (265 zones)
|   |-- models/
|       |-- bronze/         raw staging models
|       |-- silver/         cleaned trip facts
|       |-- gold/           pre-aggregated analytics tables
|
|-- dashboard/
|   |-- app.py              Streamlit dashboard
|
|-- scripts/
|   |-- run_pipeline.py     runs everything in order
|
|-- .env.example            template for your environment variables
|-- requirements.txt        Python dependencies
```

---

## Setup Guide

Follow these steps in order. Do not skip any.

---

### Before You Start

You need:
- Python 3.10 or higher installed on your machine
- An AWS account
- AWS CLI installed - follow the guide at https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

---

### Step 1 - Create an IAM User in AWS

Never use your root AWS account for day-to-day work. Create a dedicated IAM user instead.

1. Log into AWS with your root account
2. Search for IAM and open it
3. Left sidebar - Users - Create user
4. Username: nyc-taxi-user - click Next
5. Select "Attach policies directly"
6. Search and tick these policies:
   - AmazonS3FullAccess
   - AmazonAthenaFullAccess
   - AWSGlueConsoleFullAccess
   - AdministratorAccess
7. Click Next - Create user
8. Click on nyc-taxi-user - Security credentials tab
9. Scroll to Access keys - Create access key
10. Select "Local code" - tick the checkbox - Next - Create access key
11. Copy both the Access key ID and Secret access key somewhere safe. You will not see the secret again.

To enable console login for this user:
1. Still on the Security credentials tab - find "Console sign-in" - Enable console access
2. Set a custom password - untick "must change password" - Apply
3. Go to IAM Dashboard - copy the sign-in URL for IAM users
4. Use that URL to log in as nyc-taxi-user going forward

---

### Step 2 - Create the Glue IAM Role (from root account)

This is a separate role that Glue uses internally to access S3. Do this while logged in as root.

1. IAM - Roles - Create role
2. Select "AWS service" - select "Glue" - Next
3. Attach these policies:
   - AWSGlueServiceRole
   - AmazonS3FullAccess
4. Role name: nyc-taxi-glue-role - Create role
5. Click on nyc-taxi-glue-role - copy the ARN at the top. It looks like: arn:aws:iam::123456789012:role/nyc-taxi-glue-role

---

### Step 3 - Create an S3 Bucket (from IAM user account)

Log into AWS as nyc-taxi-user using the sign-in URL from Step 1.

1. Search S3 - Create bucket
2. Bucket name: nyc-taxi-data-yourname (must be globally unique, add your name)
3. Region: us-east-1
4. Leave everything else as default - Create bucket

---

### Step 4 - Clone the Repo and Install Dependencies

```
git clone https://github.com/YOUR_USERNAME/nyc-taxi-analytics.git
cd nyc-taxi-analytics
pip install -r requirements.txt
```

---

### Step 5 - Set Up Your .env File

```
cp .env.example .env
```

Open .env and fill in your values:

```
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1

S3_BUCKET_NAME=nyc-taxi-data-yourname
S3_RAW_PREFIX=raw/yellow_taxi/
S3_PROCESSED_PREFIX=processed/

ATHENA_DATABASE=nyc_taxi_db
ATHENA_WORKGROUP=primary
ATHENA_OUTPUT_LOCATION=s3://nyc-taxi-data-yourname/athena-results/

GLUE_DATABASE=nyc_taxi_db
GLUE_IAM_ROLE=arn:aws:iam::YOUR_ACCOUNT_ID:role/nyc-taxi-glue-role

START_YEAR=2024
START_MONTH=1
END_YEAR=2026
END_MONTH=3
```

---

### Step 6 - Set Up the dbt Profile

On Windows (PowerShell):
```
Copy-Item dbt_project/profiles_example.yml -Destination "$HOME/.dbt/profiles.yml"
notepad "$HOME/.dbt/profiles.yml"
```

On Mac/Linux:
```
mkdir -p ~/.dbt
cp dbt_project/profiles_example.yml ~/.dbt/profiles.yml
```

Open the file and replace YOUR-BUCKET with your actual bucket name in both places it appears. Also add your AWS credentials:

```yaml
nyc_taxi:
  target: dev
  outputs:
    dev:
      type: athena
      region_name: us-east-1
      s3_staging_dir: s3://nyc-taxi-data-yourname/athena-results/
      schema: nyc_taxi_db
      database: awsdatacatalog
      threads: 4
      aws_access_key_id: YOUR_ACCESS_KEY
      aws_secret_access_key: YOUR_SECRET_KEY
```

Test the connection:
```
cd dbt_project
dbt debug
```

You should see "All checks passed" at the bottom.

---

### Step 7 - Run Ingestion

Go back to the root folder:
```
cd ..
python ingestion/ingest.py
```

This downloads monthly Parquet files from January 2024 to March 2026 and uploads them to S3. It will take a while depending on your internet speed - expect 1 to 3 hours for the full date range.

Files already uploaded are skipped automatically, so you can safely rerun this if it gets interrupted.

---

### Step 8 - Set Up the Glue Crawler (do this manually in AWS console)

Do this after ingestion finishes.

1. Log into AWS as your IAM user
2. Search Glue - open it
3. Left sidebar - Databases - Add database - name it nyc_taxi_db - Create
4. Left sidebar - Crawlers - Create crawler
5. Crawler name: nyc-taxi-raw-crawler - Next
6. Add a data source - S3 - path: s3://nyc-taxi-data-yourname/raw/yellow_taxi/ - Add
7. Next - IAM role: select nyc-taxi-glue-role - Next
8. Target database: nyc_taxi_db - Next - Create crawler
9. Click Run crawler - wait until status shows Ready (about 5 minutes)
10. Go to Databases - nyc_taxi_db - check that a yellow_taxi table appears

Important: if the yellow_taxi table shows a "duplicate columns" error when you run dbt later, go to Glue - Tables - yellow_taxi - Edit schema - find and delete the duplicate column (usually airport_fee) - Save. Then rerun dbt.

---

### Step 9 - Run dbt

```
cd dbt_project
dbt seed
dbt run
```

This loads the taxi zone lookup table and runs all six models - bronze, silver, and four gold tables. Expect 10 to 20 minutes for the full dataset.

---

### Step 10 - Launch the Dashboard

```
cd ..
streamlit run dashboard/app.py
```

Open your browser and go to http://localhost:8501

---

## Dashboard Overview

The dashboard has four tabs:

Revenue and Fares - total revenue by borough, average fare trends over the year, monthly trip volume.

Peak Hour Demand - a heatmap showing trip volume by hour of day and day of week. Friday evenings consistently show the highest demand of the week.

Tip Behaviour - tip rates and tip amounts by time of day and borough. Only covers credit card trips since cash tips are not recorded in the dataset.

Driver Earnings - implied hourly earning rates by borough and time of day, estimated from fare, tip, and trip duration.

The sidebar lets you filter by borough, year (2024, 2025, 2026), and month.

---

## Updating the Date Range

The data currently covers January 2024 to March 2026. April 2026 is not yet published by the NYC TLC.

To extend the range when new data becomes available:

1. Update START_YEAR, START_MONTH, END_YEAR, END_MONTH in your .env file
2. Also update start_date and end_date in dbt_project/dbt_project.yml
3. Run ingestion again - it will skip months already uploaded
4. Rerun the Glue crawler from the AWS console
5. Run dbt run
6. Restart the dashboard

---

## Cost Estimate

Running this project on AWS for the full date range:

- S3 storage for roughly 4GB of Parquet files: about $0.09 per month
- Glue crawler runs: about $0.15 one-time
- Athena queries for dbt and dashboard: about $0.25 total

The whole thing costs under a dollar to run. Parquet is efficient - Athena only scans the columns it needs, and the year/month partitioning lets it skip irrelevant files entirely.

---

## Tech Stack

| Tool | Role |
|---|---|
| Python | Ingestion, validation, orchestration |
| AWS S3 | Raw data storage |
| AWS Glue | Schema catalogue |
| AWS Athena | Serverless SQL query engine |
| Great Expectations | Data quality validation |
| dbt Core | SQL transformations |
| Streamlit | Dashboard web app |
| Plotly | Interactive charts |

---

## Data Source

NYC Taxi and Limousine Commission Trip Record Data
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

Monthly Parquet files, publicly available, no license restrictions.
