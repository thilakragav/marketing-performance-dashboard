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

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Google Ads Performance",
    page_icon="🔎",
    layout="wide"
)

apply_enterprise_theme()
render_global_sidebar()

# ============================================================
# DATABASE CONNECTION
# ============================================================

from app.services.database import get_database_engine

@st.cache_resource
def get_engine():
    return get_database_engine()

engine = get_engine()

render_global_header(
    title="Google Ads Performance Intelligence",
    description="Search, Display and Performance Max campaign telemetry, ad spend, conversion efficiency and ROAS",
    icon="🔎",
    engine=engine
)

if not engine:
    st.error("Database password not configured in Streamlit secrets.")
    st.stop()

# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=300)
def load_google_ads_data():
    query = """
        SELECT
            date,
            campaign_id,
            platform,
            campaign_name,
            objective,
            spend,
            impressions,
            reach,
            clicks,
            leads,
            conversions,
            conversion_value
        FROM paid_media_daily
        WHERE platform = 'Google Ads'
        ORDER BY date
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    df["date"] = pd.to_datetime(df["date"])
    return df

try:
    gads_df = load_google_ads_data()
except Exception as e:
    st.error(f"Error loading Google Ads data: {str(e)}")
    st.stop()

min_date = gads_df["date"].min().date()
max_date = gads_df["date"].max().date()
campaigns = sorted(gads_df["campaign_name"].dropna().unique().tolist())
objectives = sorted(gads_df["objective"].dropna().unique().tolist())

# ============================================================
# FILTER BAR
# ============================================================

filters = render_filter_bar(
    min_date=min_date,
    max_date=max_date,
    campaign_options=campaigns,
    objective_options=objectives,
    key_prefix="gads"
)

curr_df = gads_df[
    (gads_df["date"] >= filters["start_date"])
    & (gads_df["date"] <= filters["end_date"])
]
if filters["selected_campaigns"]:
    curr_df = curr_df[curr_df["campaign_name"].isin(filters["selected_campaigns"])]
if filters["selected_objectives"]:
    curr_df = curr_df[curr_df["objective"].isin(filters["selected_objectives"])]

prev_df = gads_df[
    (gads_df["date"] >= filters["comp_start"])
    & (gads_df["date"] <= filters["comp_end"])
]
if filters["selected_campaigns"]:
    prev_df = prev_df[prev_df["campaign_name"].isin(filters["selected_campaigns"])]
if filters["selected_objectives"]:
    prev_df = prev_df[prev_df["objective"].isin(filters["selected_objectives"])]

if curr_df.empty:
    st.warning("No Google Ads data available for the selected filters.")
    st.stop()

# ============================================================
# METRICS & KPI CARDS
# ============================================================

curr_spend = curr_df["spend"].sum()
prev_spend = prev_df["spend"].sum() if not prev_df.empty else 0.0

curr_rev = curr_df["conversion_value"].sum()
prev_rev = prev_df["conversion_value"].sum() if not prev_df.empty else 0.0

curr_conv = curr_df["conversions"].sum()
prev_conv = prev_df["conversions"].sum() if not prev_df.empty else 0.0

curr_roas = (curr_rev / curr_spend) if curr_spend > 0 else 0.0
prev_roas = (prev_rev / prev_spend) if prev_spend > 0 else 0.0

curr_cpa = (curr_spend / curr_conv) if curr_conv > 0 else 0.0
prev_cpa = (prev_spend / prev_conv) if prev_conv > 0 else 0.0

curr_clicks = curr_df["clicks"].sum()
curr_impr = curr_df["impressions"].sum()
curr_ctr = (curr_clicks / curr_impr * 100) if curr_impr > 0 else 0.0
prev_clicks = prev_df["clicks"].sum() if not prev_df.empty else 0.0
prev_impr = prev_df["impressions"].sum() if not prev_df.empty else 0.0
prev_ctr = (prev_clicks / prev_impr * 100) if prev_impr > 0 else 0.0

currency_sym = get_currency_symbol()
comp_lbl = filters["comp_label"]
is_inc = filters["is_incomplete"]

st.subheader("Google Ads Key Performance Indicators")

row1_cols = st.columns(3)
with row1_cols[0]:
    render_kpi_card("Spend", curr_spend, prev_spend, fmt_type="currency", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row1_cols[1]:
    render_kpi_card("Revenue", curr_rev, prev_rev, fmt_type="currency", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row1_cols[2]:
    render_kpi_card("Conversions", curr_conv, prev_conv, fmt_type="integer", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)

row2_cols = st.columns(3)
with row2_cols[0]:
    render_kpi_card("ROAS", curr_roas, prev_roas, fmt_type="multiplier", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row2_cols[1]:
    render_kpi_card("CPA", curr_cpa, prev_cpa, fmt_type="currency_precise", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with row2_cols[2]:
    render_kpi_card("CTR", curr_ctr, prev_ctr, fmt_type="percentage", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)


st.divider()

# ============================================================
# CHARTS: Daily Trend & Breakdown
# ============================================================

st.subheader("📈 Performance Trends & Campaign Breakdown")

ch1, ch2, ch3 = st.columns([1.3, 1.1, 1.1])

with ch1:
    daily_gads = curr_df.groupby("date").agg(spend=("spend", "sum"), revenue=("conversion_value", "sum")).reset_index()
    daily_gads_disp = daily_gads.copy()
    daily_gads_disp["spend"] = convert_currency(daily_gads_disp["spend"])
    daily_gads_disp["revenue"] = convert_currency(daily_gads_disp["revenue"])
    fig_daily = px.line(
        daily_gads_disp,
        x="date",
        y=["spend", "revenue"],
        title=f"Google Ads Daily Spend vs Revenue ({currency_sym})",
        color_discrete_map={"spend": "#FF4D5A", "revenue": "#22C55E"},
        labels={"value": f"Amount ({currency_sym})", "variable": "Metric"}
    )
    fig_daily.update_layout(yaxis_tickprefix=currency_sym)
    apply_chart_theme(fig_daily, title=f"Google Ads Daily Spend vs Revenue ({currency_sym})", height=320)
    st.plotly_chart(fig_daily, use_container_width=True)

with ch2:
    camp_summary = curr_df.groupby("campaign_name").agg(spend=("spend", "sum"), revenue=("conversion_value", "sum"), conversions=("conversions", "sum")).reset_index()
    camp_summary["roas"] = (camp_summary["revenue"] / camp_summary["spend"]).round(2)
    camp_summary_pie = camp_summary.copy()
    camp_summary_pie["spend"] = convert_currency(camp_summary_pie["spend"])
    fig_gads_pie = px.pie(
        camp_summary_pie,
        values="spend",
        names="campaign_name",
        title=f"Spend Share by Campaign ({currency_sym})",
        hole=0.45,
        color_discrete_sequence=["#38BDF8", "#FF4D5A", "#10B981", "#F59E0B", "#818CF8"]
    )
    apply_chart_theme(fig_gads_pie, title=f"Spend Share by Campaign ({currency_sym})", height=320)
    st.plotly_chart(fig_gads_pie, use_container_width=True)

with ch3:
    fig_camp = px.bar(
        camp_summary,
        x="campaign_name",
        y="roas",
        title="ROAS by Campaign",
        text_auto=".2f",
        color="roas",
        color_continuous_scale=["#FF4D5A", "#4F8CFF", "#22C55E"]
    )
    apply_chart_theme(fig_camp, title="ROAS by Campaign", height=320)
    st.plotly_chart(fig_camp, use_container_width=True)

st.divider()

# ============================================================
# DETAILED TABLE
# ============================================================

st.subheader("📋 Campaign Detailed Table")

camp_summary_table = camp_summary.copy()
camp_summary_table["spend"] = convert_currency(camp_summary_table["spend"])
camp_summary_table["revenue"] = convert_currency(camp_summary_table["revenue"])

st.dataframe(
    camp_summary_table.style.format({
        "spend": f"{currency_sym}{{:,.2f}}",
        "revenue": f"{currency_sym}{{:,.2f}}",
        "conversions": "{:,.0f}",
        "roas": "{:.2f}x"
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# ============================================================
# AI ASSISTANT
# ============================================================

render_ai_assistant("Google Ads", active_filters=filters)
