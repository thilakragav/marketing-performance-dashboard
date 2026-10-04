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
from app.utils.currency import get_currency_symbol, convert_currency

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="GA4 Web Analytics",
    page_icon="🌐",
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
    title="Google Analytics 4 (GA4) Web Intelligence",
    description="Visitor acquisition channels, session quality, user engagement rate, goal conversions and web revenue",
    icon="🌐",
    engine=engine
)

if not engine:
    st.error("Database password is not configured.")
    st.stop()

# ==================================================
# LOAD GA4 DATA
# ==================================================

@st.cache_data(ttl=300)
def load_ga4_data():
    query = """
        SELECT
            date,
            channel,
            source,
            medium,
            users,
            new_users,
            sessions,
            engaged_sessions,
            engagement_rate,
            conversions,
            revenue
        FROM ga4_daily_channel
        ORDER BY date
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    df["date"] = pd.to_datetime(df["date"])
    return df

try:
    ga4_df = load_ga4_data()
except Exception as e:
    st.error(f"Error loading GA4 data: {str(e)}")
    st.stop()

min_date = ga4_df["date"].min().date()
max_date = ga4_df["date"].max().date()
channels = sorted(ga4_df["channel"].dropna().unique().tolist())

# ==================================================
# FILTER BAR
# ==================================================

filters = render_filter_bar(
    min_date=min_date,
    max_date=max_date,
    channel_options=channels,
    key_prefix="ga4"
)

curr_df = ga4_df[
    (ga4_df["date"] >= filters["start_date"])
    & (ga4_df["date"] <= filters["end_date"])
    & (ga4_df["channel"].isin(filters["selected_channels"]))
]

prev_df = ga4_df[
    (ga4_df["date"] >= filters["comp_start"])
    & (ga4_df["date"] <= filters["comp_end"])
    & (ga4_df["channel"].isin(filters["selected_channels"]))
]

if curr_df.empty:
    st.warning("No GA4 data available for selected filters.")
    st.stop()

# ==================================================
# KPI CALCULATIONS
# ==================================================

curr_users = curr_df["users"].sum()
prev_users = prev_df["users"].sum() if not prev_df.empty else 0.0

curr_sessions = curr_df["sessions"].sum()
prev_sessions = prev_df["sessions"].sum() if not prev_df.empty else 0.0

curr_engaged = curr_df["engaged_sessions"].sum()
curr_eng_rate = (curr_engaged / curr_sessions * 100) if curr_sessions > 0 else 0.0

prev_engaged = prev_df["engaged_sessions"].sum() if not prev_df.empty else 0.0
prev_eng_rate = (prev_engaged / prev_sessions * 100) if prev_sessions > 0 else 0.0

curr_conv = curr_df["conversions"].sum()
prev_conv = prev_df["conversions"].sum() if not prev_df.empty else 0.0

curr_rev = curr_df["revenue"].sum()
prev_rev = prev_df["revenue"].sum() if not prev_df.empty else 0.0

currency_sym = get_currency_symbol()
comp_lbl = filters["comp_label"]
is_inc = filters["is_incomplete"]

st.subheader("GA4 Web Analytics Scorecard")

row1_cols = st.columns(3)
with row1_cols[0]:
    render_kpi_card("Users", curr_users, prev_users, fmt_type="integer", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row1_cols[1]:
    render_kpi_card("Sessions", curr_sessions, prev_sessions, fmt_type="integer", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row1_cols[2]:
    render_kpi_card("Engagement Rate", curr_eng_rate, prev_eng_rate, fmt_type="percentage", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)

row2_cols = st.columns(2)
with row2_cols[0]:
    render_kpi_card("Conversions", curr_conv, prev_conv, fmt_type="integer", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row2_cols[1]:
    render_kpi_card("Revenue", curr_rev, prev_rev, fmt_type="currency", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)


st.divider()

# ==================================================
# CHARTS: Daily Traffic Trends & Channel Breakdown
# ==================================================

st.subheader("📈 Website Traffic & Engagement Trends")

ch1, ch2, ch3 = st.columns([1.3, 1.1, 1.1])

with ch1:
    daily_ga4 = curr_df.groupby("date").agg(users=("users", "sum"), sessions=("sessions", "sum")).reset_index()
    fig_traffic = px.line(
        daily_ga4,
        x="date",
        y=["users", "sessions"],
        title="Daily Visitors (Users) vs Sessions",
        color_discrete_map={"users": "#4F8CFF", "sessions": "#22C55E"}
    )
    apply_chart_theme(fig_traffic, title="Daily Visitors (Users) vs Sessions", height=320)
    st.plotly_chart(fig_traffic, use_container_width=True)

with ch2:
    ch_breakdown = curr_df.groupby("channel").agg(sessions=("sessions", "sum"), conversions=("conversions", "sum"), revenue=("revenue", "sum")).reset_index()
    fig_ga4_pie = px.pie(
        ch_breakdown,
        values="sessions",
        names="channel",
        title="Sessions Share by Channel",
        hole=0.45,
        color="channel",
        color_discrete_sequence=["#38BDF8", "#FF4D5A", "#10B981", "#F59E0B", "#818CF8"]
    )
    apply_chart_theme(fig_ga4_pie, title="Sessions Share by Channel", height=320)
    st.plotly_chart(fig_ga4_pie, use_container_width=True)

with ch3:
    fig_ch = px.bar(
        ch_breakdown,
        x="channel",
        y="sessions",
        title="Sessions by Acquisition Channel",
        text_auto=".2s",
        color="channel",
        color_discrete_sequence=["#4F8CFF", "#FF4D5A", "#22C55E", "#F59E0B"]
    )
    apply_chart_theme(fig_ch, title="Sessions by Acquisition Channel", height=320)
    st.plotly_chart(fig_ch, use_container_width=True)

st.divider()

# ==================================================
# DETAILED TABLE
# ==================================================

st.subheader("📋 Acquisition Channel Summary Table")

ch_breakdown_table = ch_breakdown.copy()
ch_breakdown_table["revenue"] = convert_currency(ch_breakdown_table["revenue"])

st.dataframe(
    ch_breakdown_table.style.format({
        "sessions": "{:,.0f}",
        "conversions": "{:,.0f}",
        "revenue": f"{currency_sym}{{:,.2f}}"
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# ==================================================
# AI ASSISTANT
# ==================================================

render_ai_assistant("GA4 Analytics", active_filters=filters)