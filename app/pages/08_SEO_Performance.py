import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

from app.components.theme import apply_enterprise_theme
from app.components.sidebar import render_global_sidebar
from app.components.header import render_global_header
from app.components.kpi_card import render_kpi_card
from app.components.filter_bar import render_filter_bar
from app.components.ai_assistant import render_ai_assistant
from app.components.charts import apply_chart_theme
from app.utils.currency import get_currency_symbol

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="SEO & Organic Search Intelligence",
    page_icon="🔍",
    layout="wide"
)

apply_enterprise_theme()
render_global_sidebar()

# ==================================================
# DATABASE CONNECTION
# ==================================================

from app.services.database import get_database_engine

@st.cache_resource
def get_engine():
    return get_database_engine()

engine = get_engine()

render_global_header(
    title="SEO & Organic Search Performance",
    description="Google Search Console organic search queries, impressions, CTR and keyword ranking positions",
    icon="🔍",
    engine=engine
)

if not engine:
    st.error("Database password is not configured.")
    st.stop()

# ==================================================
# LOAD GSC DATA
# ==================================================

@st.cache_data(ttl=300)
def load_gsc_data():
    query = """
        SELECT
            date,
            query,
            page,
            country,
            device,
            search_type,
            query_type,
            clicks,
            impressions,
            ctr,
            average_position
        FROM gsc_daily_queries
        ORDER BY date
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    df["date"] = pd.to_datetime(df["date"])
    return df

try:
    gsc_df = load_gsc_data()
except Exception as e:
    st.error(f"Error loading GSC data: {str(e)}")
    st.stop()

min_date = gsc_df["date"].min().date()
max_date = gsc_df["date"].max().date()
query_types = sorted(gsc_df["query_type"].dropna().unique().tolist())
countries = sorted(gsc_df["country"].dropna().unique().tolist())

# ==================================================
# FILTER BAR
# ==================================================

filters = render_filter_bar(
    min_date=min_date,
    max_date=max_date,
    objective_options=query_types,
    key_prefix="seo"
)

curr_df = gsc_df[
    (gsc_df["date"] >= filters["start_date"])
    & (gsc_df["date"] <= filters["end_date"])
]
if filters["selected_objectives"]:
    curr_df = curr_df[curr_df["query_type"].isin(filters["selected_objectives"])]

prev_df = gsc_df[
    (gsc_df["date"] >= filters["comp_start"])
    & (gsc_df["date"] <= filters["comp_end"])
]
if filters["selected_objectives"]:
    prev_df = prev_df[prev_df["query_type"].isin(filters["selected_objectives"])]

if curr_df.empty:
    st.warning("No SEO data available for selected filters.")
    st.stop()

# ==================================================
# KPI CALCULATIONS
# ==================================================

curr_clicks = curr_df["clicks"].sum()
prev_clicks = prev_df["clicks"].sum() if not prev_df.empty else 0.0

curr_impr = curr_df["impressions"].sum()
prev_impr = prev_df["impressions"].sum() if not prev_df.empty else 0.0

curr_ctr = (curr_clicks / curr_impr * 100) if curr_impr > 0 else 0.0
prev_ctr = (prev_clicks / prev_impr * 100) if prev_impr > 0 else 0.0

curr_pos = curr_df["average_position"].mean()
prev_pos = prev_df["average_position"].mean() if not prev_df.empty else 0.0

currency_sym = get_currency_symbol()
comp_lbl = filters["comp_label"]
is_inc = filters["is_incomplete"]

st.subheader("SEO Organic Search Scorecard")

cols = st.columns(4)
with cols[0]:
    render_kpi_card("Clicks", curr_clicks, prev_clicks, fmt_type="integer", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with cols[1]:
    render_kpi_card("Impressions", curr_impr, prev_impr, fmt_type="integer", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with cols[2]:
    render_kpi_card("CTR", curr_ctr, prev_ctr, fmt_type="percentage", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with cols[3]:
    render_kpi_card("Average Position", curr_pos, prev_pos, fmt_type="decimal", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)

st.divider()

# ==================================================
# CHARTS: Daily Search Trend & Query Breakdown
# ==================================================

st.subheader("📈 Search Trends & Top Keywords")

ch1, ch2, ch3 = st.columns([1.3, 1.1, 1.1])

with ch1:
    daily_gsc = curr_df.groupby("date").agg(clicks=("clicks", "sum"), impressions=("impressions", "sum")).reset_index()
    fig_daily = px.line(
        daily_gsc,
        x="date",
        y=["clicks", "impressions"],
        title="Organic Clicks vs Impressions Trend",
        color_discrete_map={"clicks": "#4F8CFF", "impressions": "#94A3B8"}
    )
    apply_chart_theme(fig_daily, title="Organic Clicks vs Impressions Trend", height=320)
    st.plotly_chart(fig_daily, use_container_width=True)

with ch2:
    if "query_type" in curr_df.columns:
        qt_df = curr_df.groupby("query_type")["clicks"].sum().reset_index()
        fig_query_pie = px.pie(
            qt_df,
            values="clicks",
            names="query_type",
            title="Clicks by Query Category",
            hole=0.45,
            color_discrete_sequence=["#38BDF8", "#10B981", "#F59E0B", "#FF4D5A"]
        )
    else:
        fig_query_pie = px.pie(
            query_summary.head(6),
            values="clicks",
            names="query",
            title="Top Queries Click Share",
            hole=0.45,
            color_discrete_sequence=["#38BDF8", "#10B981", "#F59E0B", "#FF4D5A", "#818CF8", "#EC4899"]
        )
    apply_chart_theme(fig_query_pie, title="Organic Click Distribution", height=320)
    st.plotly_chart(fig_query_pie, use_container_width=True)

with ch3:
    query_summary = curr_df.groupby("query").agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"), avg_pos=("average_position", "mean")).reset_index().sort_values("clicks", ascending=False).head(10)
    fig_query = px.bar(
        query_summary,
        x="query",
        y="clicks",
        title="Top 10 Organic Search Queries",
        text_auto=".2s",
        color="clicks",
        color_continuous_scale=["#4F8CFF", "#22C55E"]
    )
    apply_chart_theme(fig_query, title="Top 10 Organic Search Queries", height=320)
    st.plotly_chart(fig_query, use_container_width=True)

st.divider()

# ==================================================
# DETAILED TABLE
# ==================================================

st.subheader("📋 Search Query Detailed Table")

query_table = curr_df.groupby(["query", "query_type"]).agg(
    clicks=("clicks", "sum"),
    impressions=("impressions", "sum"),
    avg_pos=("average_position", "mean")
).reset_index().sort_values("clicks", ascending=False).head(50)

query_table["ctr"] = (query_table["clicks"] / query_table["impressions"] * 100).round(2)
query_table["avg_pos"] = query_table["avg_pos"].round(1)

st.dataframe(
    query_table.style.format({
        "clicks": "{:,.0f}",
        "impressions": "{:,.0f}",
        "ctr": "{:.2f}%",
        "avg_pos": "{:.1f}"
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# ==================================================
# AI ASSISTANT
# ==================================================

render_ai_assistant("SEO Performance", active_filters=filters)