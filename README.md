# 🚕 NYC Taxi Trip Analytics Pipeline

A complete, end-to-end data engineering project that ingests, cleans, transforms, and visualises over 3 million real New York City taxi trips — surfacing insights about fare patterns, peak demand windows, tip behaviour, and driver earnings across all five NYC boroughs.

---

## What Does This Project Actually Do?

Imagine you have 3 million rows of raw taxi trip data — messy, uncleaned, full of edge cases. A trip with a negative fare amount. A ride that lasted 0 seconds. Passenger counts of 200.

This pipeline takes all of that raw data and turns it into a clean, interactive dashboard that answers real questions:

- **When does demand surge?** (Spoiler: Friday evenings are the biggest spike of the week — bigger than any morning rush.)
- **Which zones generate higher fares?** Certain pickup areas consistently command higher average fares.
- **Who tips, and when?** Evening hours and airport trips show measurably different tipping patterns.
- **What does a driver actually earn?** We estimate implied hourly earnings by borough and time of day.

The whole thing runs on real, publicly available data from the NYC Taxi & Limousine Commission.

---

## The Big Picture — How Data Flows Through This System

Here's the journey data takes, from raw files to interactive charts:

```
NYC TLC Website (public data)
        │
        │  Python script downloads monthly Parquet files
        ▼
AWS S3 (your data lake)
        │
        │  Great Expectations checks data quality
        │  AWS Glue Crawler scans files + builds a catalogue
        ▼
AWS Athena (SQL query engine)
        │
        │  dbt runs SQL transformations in 3 layers:
        │    Bronze → Silver → Gold
        ▼
Streamlit Dashboard
        │
        │  Interactive charts in your browser
        ▼
Insights & Decisions
```

We'll go through each of these steps in plain English below.

---

## Why Each Piece Exists

### Step 1 — Getting the Data (Python + S3)

The NYC TLC publishes monthly trip records at a public URL. Each file is a compressed Parquet file (think: a smarter, smaller version of a CSV) covering all yellow cab trips in one month. A single month has ~300,000–400,000 trips.

We download these files using Python and store them in **AWS S3** — Amazon's cloud file storage. Think of S3 like a very large, very reliable hard drive in the cloud. Storing files there means:
- The data is safe and doesn't disappear when your laptop dies
- Multiple tools can read from the same place
- You only pay for what you store (~$0.023/GB/month)

> **Why not just keep them on my laptop?**
> Because 3 million rows is large (~2GB as CSV), and more importantly — cloud tools like Athena can read directly from S3 without you downloading anything locally.

### Step 2 — Checking Data Quality (Great Expectations)

Before we trust the data, we check it. Real-world data is messy. This step runs automated checks like:

- "Does the fare column exist and is it always positive?"
- "Are all location IDs valid NYC taxi zones (1–265)?"
- "Are there trips where the drop-off is before the pick-up?"

If critical checks fail, the pipeline stops and tells you. This prevents bad data from silently corrupting your analytics further down the line.

### Step 3 — Making the Data Queryable (AWS Glue + Athena)

Here's a problem: your data is in S3 as Parquet files, but SQL tools don't speak "Parquet file on S3" — they speak "table in a database."

**AWS Glue** solves this. It scans your S3 files (this is called "crawling"), figures out what columns exist and what types they are, and registers the result in a catalogue. Now other tools know: "there's a table called `yellow_taxi` with columns like `fare_amount` and `pickup_datetime`."

**AWS Athena** is a query engine that reads from S3 directly, using the catalogue that Glue built. You write SQL, Athena runs it against the files in S3, and you get results back — without needing a traditional database server running 24/7.

> **Why is this cheaper than a normal database?**
> Athena charges per query ($5 per TB scanned). For analytics that run a few times a day, this is far cheaper than keeping a database server running constantly. For this project, most queries cost fractions of a cent.

### Step 4 — Transforming the Data (dbt)

Raw data is messy. Column names are cryptic (what is `VendorID`?). Values are coded numbers (payment type `1` means "credit card"). Some rows are junk (fare = -$500?).

**dbt** (data build tool) runs SQL transformations to turn raw data into clean, analysis-ready tables. We use a 3-layer approach:

#### 🟫 Bronze Layer — "Just Get It In"
A thin wrapper over the raw S3 data. Minimal changes — just cast types and rename a few columns. If the raw data changes, we can trace it back here.

#### 🪨 Silver Layer — "Clean It Up"
This is where the real transformation happens:
- Remove impossible trips (negative fares, zero-second rides, invalid locations)
- Add calculated fields: trip duration, fare per mile, tip percentage
- Decode cryptic numbers into human-readable labels ("Credit Card", "JFK Airport", etc.)
- Add time breakdowns: hour of day, day of week, "Morning Rush", "Evening Rush", etc.

After the silver layer, every row represents **one valid, cleaned taxi trip**.

#### 🥇 Gold Layer — "Answer the Questions"
Pre-aggregated tables designed to answer specific questions fast. Instead of summing 3 million rows every time the dashboard loads, we pre-compute the aggregates:
- `agg_fare_analytics` — average fare by borough, zone, and month
- `agg_peak_hour_demand` — trip volume by hour × day of week × borough
- `agg_tip_behavior` — tip rates and tip amounts by time, borough, payment type
- `agg_driver_earnings` — implied earnings per hour by borough and time of day

The dashboard only ever queries these gold tables — which is why it loads fast.

### Step 5 — The Dashboard (Streamlit + Plotly)

A Python-based web app that connects to Athena, pulls the gold layer data, and renders interactive charts. No JavaScript required — it's all Python.

---

## What You'll See in the Dashboard

### 📊 Revenue & Fares
- Total revenue broken down by borough
- Average fare trend across the year
- Monthly trip volume by borough

### 🕐 Peak Hour Demand
- A heatmap showing every hour × day of week combination
- Friday evening (5–8pm) consistently stands out as the highest-demand window — more than morning rush hour
- This insight directly informs dynamic pricing strategy

### 💵 Tip Behaviour
- Credit card tip rates by time of day
- Borough-by-borough tip comparison
- Airport trips vs regular trips — airport trips consistently attract higher tips
- Note: Cash tips aren't recorded in the dataset, so this analysis covers credit card trips only

### 🚗 Driver Earnings
- Implied hourly earnings rate by borough and time bucket
- Distribution of earnings per trip
- Which zones and times maximise driver income

---

## Project Structure

```
nyc-taxi-analytics/
│
├── ingestion/
│   ├── ingest.py           ← Downloads data from NYC TLC, uploads to S3
│   └── setup_glue.py       ← Creates Glue database, crawler, runs it
│
├── great_expectations_suite/
│   └── validate.py         ← Data quality checks before transformation
│
├── dbt_project/
│   ├── dbt_project.yml     ← dbt configuration
│   ├── profiles_example.yml← How to connect dbt to Athena (copy to ~/.dbt/)
│   ├── seeds/
│   │   └── taxi_zones.csv  ← NYC taxi zone lookup table (265 zones)
│   └── models/
│       ├── bronze/         ← Raw staging models
│       │   ├── sources.yml
│       │   └── stg_yellow_taxi.sql
│       ├── silver/         ← Cleaned trip facts
│       │   └── fct_trips.sql
│       └── gold/           ← Pre-aggregated analytics
│           ├── agg_fare_analytics.sql
│           ├── agg_peak_hour_demand.sql
│           ├── agg_tip_behavior.sql
│           └── agg_driver_earnings.sql
│
├── dashboard/
│   └── app.py              ← Streamlit dashboard (run this last)
│
├── scripts/
│   └── run_pipeline.py     ← Runs everything in order (one command)
│
├── .env.example            ← Template for your environment variables
├── requirements.txt        ← Python dependencies
└── README.md               ← You are here
```

---

## Setup Guide

Follow these steps in order. Each step builds on the last.

### Prerequisites

Before you start, you need:
- Python 3.10 or higher
- An AWS account (free tier works for small volumes)
- AWS CLI installed and configured on your machine

If you don't have the AWS CLI set up yet, follow [this guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). It takes about 10 minutes.

---

### Step 1 — Clone the repo and install Python dependencies

```bash
git clone https://github.com/YOUR_USERNAME/nyc-taxi-analytics.git
cd nyc-taxi-analytics

pip install -r requirements.txt
```

This installs everything: boto3 (AWS SDK), dbt, Streamlit, Plotly, and more.

---

### Step 2 — Set up your environment variables

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in your values:

```
AWS_ACCESS_KEY_ID=...       ← Your AWS access key
AWS_SECRET_ACCESS_KEY=...   ← Your AWS secret key
AWS_REGION=us-east-1        ← Your preferred AWS region
S3_BUCKET_NAME=...          ← A bucket you created in S3 (must exist)
ATHENA_DATABASE=nyc_taxi_db
ATHENA_OUTPUT_LOCATION=s3://your-bucket/athena-results/
GLUE_IAM_ROLE=...           ← ARN of an IAM role with Glue + S3 access
```

#### How to create an S3 bucket
1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com)
2. Click "Create bucket"
3. Give it a unique name (e.g. `myname-nyc-taxi-data`)
4. Leave everything else at defaults → Create

#### How to create the Glue IAM role
1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam)
2. Click Roles → Create role
3. Choose "AWS service" → "Glue"
4. Attach these policies:
   - `AWSGlueServiceRole`
   - `AmazonS3FullAccess` (or a scoped-down version for your bucket)
5. Name it something like `GlueS3Role` → Create
6. Copy the role ARN and paste it into `.env` as `GLUE_IAM_ROLE`

---

### Step 3 — Set up dbt to connect to Athena

dbt needs a connection profile. Copy the example:

```bash
# This file lives outside the project (keeps credentials safe)
mkdir -p ~/.dbt
cp dbt_project/profiles_example.yml ~/.dbt/profiles.yml
```

Edit `~/.dbt/profiles.yml` and replace `YOUR-BUCKET` with your actual S3 bucket name.

Test the connection:
```bash
cd dbt_project
dbt debug
```

You should see "All checks passed!" at the bottom.

---

### Step 4 — Run the pipeline

```bash
python scripts/run_pipeline.py
```

This runs all 4 steps automatically:
1. Downloads NYC TLC data for Jan–Dec 2023 and uploads to S3 (~2–4 hours for full year, depending on your internet speed)
2. Validates data quality
3. Creates and runs the Glue crawler (~5 minutes)
4. Runs all dbt models on Athena (~10–20 minutes for 3M rows)

You can also run each step individually if you prefer:

```bash
# Just ingestion
python ingestion/ingest.py --start-year 2023 --start-month 1 --end-year 2023 --end-month 3

# Just validation
python great_expectations_suite/validate.py

# Just Glue setup
python ingestion/setup_glue.py

# Just dbt
cd dbt_project
dbt seed        # loads the taxi zone lookup table
dbt run         # runs all SQL models
dbt test        # runs data quality tests
```

---

### Step 5 — Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open your browser to `http://localhost:8501`. You'll see the dashboard with all four tabs.

---

## Cost Estimate

Running this project for one year of data:

| Service | Usage | Estimated Cost |
|---|---|---|
| S3 Storage | ~3GB of Parquet | ~$0.07/month |
| Glue Crawler | ~10 minutes of crawling | ~$0.15 one-time |
| Athena Queries | ~50GB scanned (dbt + dashboard) | ~$0.25 |
| **Total** | | **~$0.50** |

This is genuinely inexpensive. The Parquet format is highly efficient — Athena only scans the columns it needs, and the partitioning (by year/month) means it can skip entire months of data when your query doesn't need them.

---

## Key Insights From the Data

These are real patterns from the 2023 NYC yellow cab dataset:

**Demand**
- Friday evenings (5–8pm) are the single highest-demand window of the week — surpassing every morning rush hour
- Trip volume dips sharply after midnight and recovers slowly from 5am onward
- Manhattan dominates in raw trip volume, but Queens and Brooklyn show strong weekend patterns

**Fares**
- Airport rate code trips (JFK, Newark) have significantly higher average fares — roughly 2–3x the standard rate
- The fare-per-mile rate is actually lower for very long trips, as the meter rate structure favours shorter, urban rides

**Tips**
- Credit card tip rates are highest during evening hours (6pm–11pm)
- Airport trips attract higher tip percentages on average
- Weekday tipping slightly outpaces weekend tipping, likely reflecting business travellers vs leisure

**Driver Earnings**
- Manhattan pickups during morning and evening rush hours show the highest implied hourly earning rates
- Late-night shifts (12am–4am) have fewer trips but higher average fares per trip

---

## Tech Stack Summary

| Tool | What It Does | Why We Chose It |
|---|---|---|
| Python | Ingestion, validation, orchestration | Widely known, excellent AWS libraries |
| AWS S3 | Raw data storage (data lake) | Cheap, durable, works with everything |
| AWS Glue | Schema catalogue (what columns exist) | Integrates natively with S3 + Athena |
| AWS Athena | SQL query engine over S3 | Serverless, pay-per-query, no DB to manage |
| Great Expectations | Data quality validation | Industry standard for pipeline data checks |
| dbt Core | SQL transformations (Bronze/Silver/Gold) | Modular, testable, version-controlled SQL |
| Streamlit | Dashboard web app | Fast to build, pure Python, no JavaScript |
| Plotly | Interactive charts | Beautiful, interactive, well-documented |

---

## Data Source

**NYC Taxi & Limousine Commission (TLC) Trip Record Data**
- URL: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- Format: Parquet files, one per month
- License: Public domain — free to use

The TLC has published this data since 2009. This project uses 2023 yellow cab records.

---

## Questions or Issues?

If something breaks:
1. Check your `.env` file — most errors come from missing or wrong values there
2. Run `dbt debug` to verify the Athena connection
3. Check the AWS console to make sure your Glue crawler ran successfully
4. Open an issue on this repo with the error message

---

*Built with Python, dbt, AWS, and a lot of taxi data.*
