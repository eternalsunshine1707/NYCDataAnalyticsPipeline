"""
dashboard/app.py
─────────────────────────────────────────────────────────────────────────────
NYC Taxi Trip Analytics Dashboard
─────────────────────────────────────────────────────────────────────────────
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import awswrangler as wr
import boto3
from dotenv import load_dotenv

load_dotenv()

# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NYC Taxi Analytics",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
        [data-testid="stHeader"] { background-color: #1A0933 !important; }
        header { background-color: #1A0933 !important; }
        .stApp { background-color: #1A0933; }
        [data-testid="stSidebar"] { background-color: #1A0933 !important; }
        [data-testid="stSidebar"] * { color: #FFFFFF !important; }
        h1, h2, h3, h4, h5, h6 { color: #F7C948 !important; }
        p, span, div, label { color: #FFFFFF !important; }
        [data-testid="stMetric"] { background-color: #2D1155; border-radius: 10px; padding: 10px; }
        [data-testid="stMetricLabel"] { color: #FFFFFF !important; }
        [data-testid="stMetricValue"] { color: #F7C948 !important; }
        .stTabs [data-baseweb="tab"] { color: #FFFFFF !important; }
        .stTabs [data-baseweb="tab-list"] { background-color: #2D1155; }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: #6B35A8 !important;
            color: #FFFFFF !important;
        }
        .stPlotlyChart { background-color: #2D1155; border-radius: 10px; }
        a { color: #F7C948 !important; }
        [data-testid="stInfo"] { background-color: #2D1155 !important; color: #FFFFFF !important; }
        .block-container { padding-top: 1rem !important; }
        /* Fix all dropdown visibility */
        div[data-baseweb="select"] span { color: #FFFFFF !important; }
        div[data-baseweb="select"] div { background-color: #2D1155 !important; color: #FFFFFF !important; }
        ul[data-baseweb="menu"] { background-color: #2D1155 !important; }
        ul[data-baseweb="menu"] li { color: #FFFFFF !important; }
        ul[data-baseweb="menu"] li:hover { background-color: #6B35A8 !important; color: #FFFFFF !important; }
        div[role="listbox"] { background-color: #2D1155 !important; }
        div[role="listbox"] * { color: #FFFFFF !important; }
        div[role="option"] { background-color: #2D1155 !important; color: #FFFFFF !important; }
        div[role="option"]:hover { background-color: #6B35A8 !important; }
        /* Dropdown input text */
        .stMultiSelect div div div div { color: #FFFFFF !important; }
        input { color: #FFFFFF !important; background-color: #2D1155 !important; }
        /* Override white background on dropdown container */
        div[data-baseweb="popover"] div { background-color: #2D1155 !important; color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# ── Colour Palette ─────────────────────────────────────────────────────────────

COLORS = {
    "yellow": "#F7C948",
    "dark": "#1A1A2E",
    "blue": "#4A90D9",
    "green": "#2ECC71",
    "red": "#E74C3C",
    "purple": "#9B59B6",
    "orange": "#E67E22",
}

BOROUGH_COLORS = {
    "Manhattan": "#F7C948",
    "Brooklyn": "#4A90D9",
    "Queens": "#2ECC71",
    "Bronx": "#E74C3C",
    "Staten Island": "#9B59B6",
    "EWR": "#E67E22",
}

# ── AWS Config ─────────────────────────────────────────────────────────────────

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "nyc_taxi_db")
ATHENA_OUTPUT = os.getenv("ATHENA_OUTPUT_LOCATION", "")
GOLD_SCHEMA = "nyc_taxi_db_gold"
SILVER_SCHEMA = "nyc_taxi_db_silver"


# ── Data Loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_fare_analytics() -> pd.DataFrame:
    boto3_session = boto3.Session(region_name=AWS_REGION)
    query = f"""
        SELECT *
        FROM "{GOLD_SCHEMA}"."agg_fare_analytics"
        WHERE pickup_borough NOT IN ('Unknown', 'EWR')
    """
    return wr.athena.read_sql_query(
        sql=query,
        database=ATHENA_DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=boto3_session,
    )


@st.cache_data(ttl=3600)
def load_peak_hour_demand() -> pd.DataFrame:
    boto3_session = boto3.Session(region_name=AWS_REGION)
    query = f"""
        SELECT *
        FROM "{GOLD_SCHEMA}"."agg_peak_hour_demand"
        WHERE pickup_borough NOT IN ('Unknown', 'EWR')
    """
    return wr.athena.read_sql_query(
        sql=query,
        database=ATHENA_DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=boto3_session,
    )


@st.cache_data(ttl=3600)
def load_tip_behavior() -> pd.DataFrame:
    boto3_session = boto3.Session(region_name=AWS_REGION)
    query = f"""
        SELECT *
        FROM "{GOLD_SCHEMA}"."agg_tip_behavior"
        WHERE pickup_borough NOT IN ('Unknown', 'EWR')
    """
    return wr.athena.read_sql_query(
        sql=query,
        database=ATHENA_DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=boto3_session,
    )


@st.cache_data(ttl=3600)
def load_driver_earnings() -> pd.DataFrame:
    boto3_session = boto3.Session(region_name=AWS_REGION)
    query = f"""
        SELECT *
        FROM "{GOLD_SCHEMA}"."agg_driver_earnings"
        WHERE pickup_borough NOT IN ('Unknown', 'EWR')
    """
    return wr.athena.read_sql_query(
        sql=query,
        database=ATHENA_DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=boto3_session,
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────

def render_sidebar():
    st.sidebar.title("🚕 NYC Taxi Analytics")
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")

    boroughs = st.sidebar.multiselect(
        "Select Boroughs",
        options=["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"],
        default=["Manhattan", "Brooklyn", "Queens", "Bronx"],
    )

    years = st.sidebar.multiselect(
        "Select Years",
        options=[2024, 2025, 2026],
        default=[2024, 2025, 2026],
    )

    months = st.sidebar.multiselect(
        "Select Months",
        options=list(range(1, 13)),
        format_func=lambda x: [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ][x - 1],
        default=list(range(1, 13)),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Data Source:** [NYC TLC Open Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)\n\n"
        "**Pipeline:** Python → S3 → Glue → dbt → Athena → Streamlit"
    )

    return boroughs, months, years


# ── Chart Components ───────────────────────────────────────────────────────────

def chart_revenue_by_borough(df: pd.DataFrame):
    grouped = (
        df[df["pickup_borough"].isin(df["pickup_borough"].unique())]
        .groupby("pickup_borough")
        .agg(total_revenue=("total_gross_revenue", "sum"), total_trips=("total_trips", "sum"))
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )
    fig = px.bar(
        grouped,
        x="pickup_borough",
        y="total_revenue",
        color="pickup_borough",
        color_discrete_map=BOROUGH_COLORS,
        title="Total Revenue by Borough",
        labels={"pickup_borough": "Borough", "total_revenue": "Total Revenue ($)"},
        text_auto=".3s",
    )
    fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
    return fig


def chart_avg_fare_by_borough(df: pd.DataFrame):
    grouped = (
        df.groupby(["pickup_borough", "pickup_month_num"])
        .agg(avg_fare=("avg_fare_amount", "mean"))
        .reset_index()
    )
    fig = px.line(
        grouped,
        x="pickup_month_num",
        y="avg_fare",
        color="pickup_borough",
        color_discrete_map=BOROUGH_COLORS,
        title="Average Fare by Borough Over the Year",
        labels={"pickup_month_num": "Month", "avg_fare": "Avg Fare ($)", "pickup_borough": "Borough"},
        markers=True,
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    return fig


def chart_heatmap_demand(df: pd.DataFrame):
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = (
        df.groupby(["day_of_week_name", "hour_of_day"])
        .agg(total_trips=("total_trips", "sum"))
        .reset_index()
        .pivot(index="day_of_week_name", columns="hour_of_day", values="total_trips")
        .reindex(day_order)
        .fillna(0)
    )
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[f"{h}:00" for h in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            colorbar=dict(title="Trips"),
        )
    )
    fig.update_layout(
        title="Trip Volume Heatmap: Day of Week × Hour of Day",
        xaxis_title="Hour of Day",
        yaxis_title="Day of Week",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def chart_tip_rate_by_time(df: pd.DataFrame):
    time_order = [
        "Late Night (12am-6am)",
        "Morning Rush (6am-10am)",
        "Mid Morning (10am-12pm)",
        "Lunch (12pm-2pm)",
        "Afternoon (2pm-5pm)",
        "Evening Rush (5pm-8pm)",
        "Evening (8pm-11pm)",
        "Late Night (11pm-12am)",
    ]
    grouped = (
        df.groupby("time_of_day_bucket")
        .agg(avg_tip_rate=("tip_rate_pct", "mean"), avg_tip_pct=("avg_tip_pct_of_fare", "mean"))
        .reset_index()
    )
    grouped["order"] = grouped["time_of_day_bucket"].map(
        {v: i for i, v in enumerate(time_order)}
    )
    grouped = grouped.sort_values("order")
    fig = px.bar(
        grouped,
        x="time_of_day_bucket",
        y="avg_tip_pct",
        title="Average Tip % of Fare by Time of Day (Credit Card Trips)",
        labels={"time_of_day_bucket": "Time of Day", "avg_tip_pct": "Avg Tip (% of Fare)"},
        color="avg_tip_pct",
        color_continuous_scale="Greens",
    )
    fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-30)
    return fig


def chart_driver_earnings_distribution(df: pd.DataFrame):
    grouped = (
        df.groupby(["pickup_borough", "time_of_day_bucket"])
        .agg(avg_hourly=("avg_implied_hourly_rate", "mean"))
        .reset_index()
    )
    fig = px.bar(
        grouped,
        x="time_of_day_bucket",
        y="avg_hourly",
        color="pickup_borough",
        color_discrete_map=BOROUGH_COLORS,
        barmode="group",
        title="Implied Hourly Earnings by Borough and Time of Day",
        labels={
            "time_of_day_bucket": "Time of Day",
            "avg_hourly": "Implied Hourly Rate ($/hr)",
            "pickup_borough": "Borough",
        },
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-30)
    return fig


def chart_monthly_trips(df: pd.DataFrame):
    grouped = (
        df.groupby(["pickup_month_num", "pickup_borough"])
        .agg(total_trips=("total_trips", "sum"))
        .reset_index()
    )
    fig = px.line(
        grouped,
        x="pickup_month_num",
        y="total_trips",
        color="pickup_borough",
        color_discrete_map=BOROUGH_COLORS,
        title="Monthly Trip Volume by Borough",
        labels={"pickup_month_num": "Month", "total_trips": "Total Trips", "pickup_borough": "Borough"},
        markers=True,
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    return fig


# ── KPI Cards ──────────────────────────────────────────────────────────────────

def render_kpi_cards(fare_df: pd.DataFrame, demand_df: pd.DataFrame):
    total_trips = int(fare_df["total_trips"].sum())
    total_revenue = fare_df["total_gross_revenue"].sum()
    avg_fare = fare_df["avg_fare_amount"].mean()
    avg_tip_pct = fare_df["avg_tip_pct"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("🚖 Total Trips", f"{total_trips:,.0f}")
    with col2:
        st.metric("💰 Total Revenue", f"${total_revenue:,.0f}")
    with col3:
        st.metric("🎯 Avg Fare", f"${avg_fare:.2f}")
    with col4:
        st.metric("💡 Avg Tip %", f"{avg_tip_pct:.1f}%")
    with col5:
        peak_day = (
            demand_df.groupby("day_of_week_name")["total_trips"]
            .sum()
            .idxmax()
        )
        st.metric("📈 Busiest Day", peak_day)


# ── Main App ───────────────────────────────────────────────────────────────────

def main():
    boroughs, months, years = render_sidebar()

    st.markdown("""
        <h1 style='text-align: center; text-decoration: underline; color: white;'>
            🚕 NYC Yellow Cab Trip Analytics
        </h1>
    """, unsafe_allow_html=True)

    st.markdown(
        "Analysing **3M+ real taxi trips** from the NYC Taxi & Limousine Commission dataset. "
        "Data flows through: **S3 → Glue → dbt (Athena) → this dashboard**."
    )
    st.markdown("---")

    with st.spinner("Loading data from Athena..."):
        try:
            fare_df = load_fare_analytics()
            demand_df = load_peak_hour_demand()
            tip_df = load_tip_behavior()
            earn_df = load_driver_earnings()
        except Exception as e:
            st.error(f"Failed to connect to Athena: {e}")
            st.info("Make sure your AWS credentials are configured and the dbt models have been run.")
            st.stop()

    fare_df = fare_df[
        fare_df["pickup_borough"].isin(boroughs) &
        fare_df["pickup_month_num"].isin(months) &
        fare_df["pickup_year"].isin(years)
    ]
    demand_df = demand_df[
        demand_df["pickup_borough"].isin(boroughs) &
        demand_df["pickup_month_num"].isin(months) &
        demand_df["pickup_year"].isin(years)
    ]
    tip_df = tip_df[
        tip_df["pickup_borough"].isin(boroughs) &
        tip_df["pickup_month_num"].isin(months) &
        tip_df["pickup_year"].isin(years)
    ]
    earn_df = earn_df[
        earn_df["pickup_borough"].isin(boroughs) &
        earn_df["pickup_month_num"].isin(months) &
        earn_df["pickup_year"].isin(years)
    ]

    if fare_df.empty:
        st.warning("No data found for the selected filters.")
        st.stop()

    render_kpi_cards(fare_df, demand_df)
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Revenue & Fares",
        "🕐 Peak Hour Demand",
        "💵 Tip Behaviour",
        "🚗 Driver Earnings",
    ])

    with tab1:
        st.subheader("Revenue & Fare Analytics")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(chart_revenue_by_borough(fare_df), use_container_width=True)
        with col2:
            st.plotly_chart(chart_avg_fare_by_borough(fare_df), use_container_width=True)
        st.plotly_chart(chart_monthly_trips(demand_df), use_container_width=True)

    with tab2:
        st.subheader("When Do People Take Taxis?")
        st.markdown(
            "The heatmap below shows trip volume for every combination of day and hour. "
            "**Darker = more trips.** Look for the Friday evening spike."
        )
        st.plotly_chart(chart_heatmap_demand(demand_df), use_container_width=True)

        friday_evening = demand_df[
            (demand_df["day_of_week_name"] == "Friday") &
            (demand_df["hour_of_day"].between(17, 19))
        ]["total_trips"].sum()
        monday_morning = demand_df[
            (demand_df["day_of_week_name"] == "Monday") &
            (demand_df["hour_of_day"].between(7, 9))
        ]["total_trips"].sum()

        if monday_morning > 0:
            pct_higher = (friday_evening - monday_morning) / monday_morning * 100
            st.info(
                f"📌 **Key Insight:** Friday evening (5–8pm) generates **{pct_higher:.0f}% more trips** "
                f"than Monday morning rush — making it the single highest-demand window of the week."
            )

    with tab3:
        st.subheader("Tip Behaviour Patterns (Credit Card Trips Only)")
        st.markdown(
            "Note: Cash tips aren't recorded in the dataset. "
            "This analysis focuses on credit card transactions where tip data is reliable."
        )
        st.plotly_chart(chart_tip_rate_by_time(tip_df), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            borough_tips = (
                tip_df.groupby("pickup_borough")
                .agg(avg_tip_rate=("tip_rate_pct", "mean"))
                .reset_index()
                .sort_values("avg_tip_rate", ascending=True)
            )
            fig = px.bar(
                borough_tips,
                x="avg_tip_rate",
                y="pickup_borough",
                orientation="h",
                title="Tip Rate by Borough (%)",
                color="pickup_borough",
                color_discrete_map=BOROUGH_COLORS,
                labels={"avg_tip_rate": "Tip Rate (%)", "pickup_borough": "Borough"},
            )
            fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            airport_tips = (
                tip_df.groupby("is_airport_trip")
                .agg(avg_tip_pct=("avg_tip_pct_of_fare", "mean"))
                .reset_index()
            )
            airport_tips["label"] = airport_tips["is_airport_trip"].map(
                {True: "Airport Trip", False: "Regular Trip"}
            )
            fig = px.bar(
                airport_tips,
                x="label",
                y="avg_tip_pct",
                title="Avg Tip % — Airport vs Regular Trips",
                color="label",
                color_discrete_sequence=[COLORS["blue"], COLORS["yellow"]],
                labels={"label": "Trip Type", "avg_tip_pct": "Avg Tip (% of Fare)"},
                text_auto=".1f",
            )
            fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Driver Earnings Distribution")
        st.markdown(
            "The charts below show the **implied hourly earnings rate** "
            "— estimated from trip fare, tip, and duration. "
            "This is a proxy for real earnings (before platform fees)."
        )
        st.plotly_chart(chart_driver_earnings_distribution(earn_df), use_container_width=True)

        top_zones = (
            earn_df.groupby("pickup_borough")
            .agg(
                avg_earn=("avg_earnings_per_trip", "mean"),
                avg_hourly=("avg_implied_hourly_rate", "mean"),
            )
            .reset_index()
            .sort_values("avg_earn", ascending=False)
        )

        st.subheader("Average Earnings Summary by Borough")
        st.dataframe(
            top_zones.rename(columns={
                "pickup_borough": "Borough",
                "avg_earn": "Avg Earnings/Trip ($)",
                "avg_hourly": "Implied Hourly Rate ($/hr)",
            }).style.format({
                "Avg Earnings/Trip ($)": "${:.2f}",
                "Implied Hourly Rate ($/hr)": "${:.2f}",
            }),
            use_container_width=True,
        )

    st.markdown("---")
    st.caption(
        "Data: NYC TLC Yellow Cab Trip Records | "
        "Pipeline: Python + AWS S3/Glue/Athena + dbt Core | "
        "Dashboard: Streamlit + Plotly"
    )


if __name__ == "__main__":
    main()