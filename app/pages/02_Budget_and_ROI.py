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
from app.components.badges import render_status_badge
from app.utils.currency import get_currency_symbol, convert_currency

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Budget & ROI Intelligence",
    page_icon="💰",
    layout="wide"
)

apply_enterprise_theme()
render_global_sidebar()

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

from app.services.database import get_database_engine

@st.cache_resource
def get_engine():
    return get_database_engine()

engine = get_engine()

render_global_header(
    title="Budget & ROI Intelligence",
    description="Marketing capital allocation, pacing variance, expenditure forecasting, ROAS thresholds and net return analysis",
    icon="💰",
    engine=engine
)

if not engine:
    st.error("Database connection is not configured.")
    st.stop()

# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=300)
def load_paid_media_budget():
    query = """
        SELECT
            date,
            campaign_id,
            platform,
            campaign_name,
            objective,
            spend,
            conversions,
            conversion_value,
            approved_budget,
            daily_budget,
            days_elapsed,
            expected_spend_to_date,
            pacing_variance,
            forecast_spend,
            budget_utilization,
            budget_status,
            roi_status
        FROM paid_media_daily
        ORDER BY date
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    df["date"] = pd.to_datetime(df["date"])
    return df

@st.cache_data(ttl=300)
def load_campaign_performance_budget():
    query = """
        SELECT
            campaign_id,
            platform,
            campaign_name,
            objective,
            spend,
            revenue,
            conversions,
            approved_budget,
            target_conversions,
            "target_CPA",
            target_revenue,
            "target_ROAS",
            cpa,
            roas,
            roi,
            budget_utilization
        FROM campaign_performance
        ORDER BY spend DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df

try:
    paid_media_df = load_paid_media_budget()
    campaign_df = load_campaign_performance_budget()
except Exception as e:
    st.error(f"Error loading budget data from PostgreSQL: {str(e)}")
    st.stop()

min_date = paid_media_df["date"].min().date()
max_date = paid_media_df["date"].max().date()
channels = sorted(paid_media_df["platform"].unique().tolist())
campaign_names = sorted(paid_media_df["campaign_name"].dropna().unique().tolist())

# ============================================================
# FILTER BAR
# ============================================================

filters = render_filter_bar(
    min_date=min_date,
    max_date=max_date,
    channel_options=channels,
    campaign_options=campaign_names,
    key_prefix="budget"
)

# Current period data
curr_paid = paid_media_df[
    (paid_media_df["date"] >= filters["start_date"])
    & (paid_media_df["date"] <= filters["end_date"])
    & (paid_media_df["platform"].isin(filters["selected_channels"]))
]
if filters["selected_campaigns"]:
    curr_paid = curr_paid[curr_paid["campaign_name"].isin(filters["selected_campaigns"])]

# Previous comparison data
prev_paid = paid_media_df[
    (paid_media_df["date"] >= filters["comp_start"])
    & (paid_media_df["date"] <= filters["comp_end"])
    & (paid_media_df["platform"].isin(filters["selected_channels"]))
]
if filters["selected_campaigns"]:
    prev_paid = prev_paid[prev_paid["campaign_name"].isin(filters["selected_campaigns"])]

# Filter campaigns table by channel/campaign
curr_campaigns = campaign_df[campaign_df["platform"].isin(filters["selected_channels"])].copy()
if filters["selected_campaigns"]:
    curr_campaigns = curr_campaigns[curr_campaigns["campaign_name"].isin(filters["selected_campaigns"])]

# ============================================================
# COMPUTE KPI METRICS
# ============================================================

# Budgets from active campaigns
allocated_budget = curr_campaigns["approved_budget"].sum()
actual_spend = curr_paid["spend"].sum() if not curr_paid.empty else 0.0
prev_spend = prev_paid["spend"].sum() if not prev_paid.empty else 0.0

remaining_budget = max(0.0, allocated_budget - actual_spend)
budget_utilization = (actual_spend / allocated_budget * 100) if allocated_budget > 0 else 0.0

expected_spend = curr_paid["expected_spend_to_date"].dropna().iloc[-1] if not curr_paid.empty and not curr_paid["expected_spend_to_date"].dropna().empty else actual_spend
pacing_variance = actual_spend - expected_spend
forecast_spend = curr_paid["forecast_spend"].dropna().iloc[-1] if not curr_paid.empty and not curr_paid["forecast_spend"].dropna().empty else actual_spend

curr_rev = curr_paid["conversion_value"].sum() if not curr_paid.empty else 0.0
prev_rev = prev_paid["conversion_value"].sum() if not prev_paid.empty else 0.0

roas = (curr_rev / actual_spend) if actual_spend > 0 else 0.0
prev_roas = (prev_rev / prev_spend) if prev_spend > 0 else 0.0

roi = ((curr_rev - actual_spend) / actual_spend * 100) if actual_spend > 0 else 0.0
prev_roi = ((prev_rev - prev_spend) / prev_spend * 100) if prev_spend > 0 else 0.0

currency_sym = get_currency_symbol()
comp_lbl = filters["comp_label"]
is_inc = filters["is_incomplete"]

# Status Badges Determination
if budget_utilization > 105:
    pacing_tag = "OVERSPENDING"
elif budget_utilization < 70:
    pacing_tag = "UNDERSPENDING"
elif budget_utilization > 0:
    pacing_tag = "ON TRACK"
else:
    pacing_tag = "INSUFFICIENT DATA"

if roi > 0:
    roi_tag = "POSITIVE ROI"
elif roi == 0 and actual_spend > 0:
    roi_tag = "BREAK-EVEN"
elif actual_spend > 0:
    roi_tag = "NEGATIVE ROI"
else:
    roi_tag = "INSUFFICIENT DATA"

# Status Badges Banner
st.markdown(
    f"""
    <div style="display: flex; gap: 12px; margin-bottom: 16px; align-items: center;">
        <span style="font-size: 0.82rem; color: #94A3B8; font-weight: 500;">Pacing Status:</span>
        {render_status_badge(pacing_tag)}
        <span style="font-size: 0.82rem; color: #94A3B8; font-weight: 500; margin-left: 12px;">Profitability:</span>
        {render_status_badge(roi_tag)}
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# KPI CARDS ROW:
# Allocated Budget, Actual Spend, Remaining Budget, Budget Utilization, Expected Spend, Pacing Variance, Forecast Spend, ROAS, ROI
# ============================================================

st.subheader("Budget & Pacing Metrics")

b_row1 = st.columns(3)
with b_row1[0]:
    render_kpi_card("Spend", allocated_budget, None, fmt_type="currency", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl)
with b_row1[1]:
    render_kpi_card("Actual Spend", actual_spend, prev_spend, fmt_type="currency", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with b_row1[2]:
    render_kpi_card("Remaining Budget", remaining_budget, None, fmt_type="currency", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl)

b_row2 = st.columns(3)
with b_row2[0]:
    render_kpi_card("Budget Utilization", budget_utilization, None, fmt_type="percentage", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl)
with b_row2[1]:
    render_kpi_card("Expected Spend", expected_spend, None, fmt_type="currency", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl)
with b_row2[2]:
    render_kpi_card("Pacing Variance", pacing_variance, None, fmt_type="currency", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl)

b_row3 = st.columns(3)
with b_row3[0]:
    render_kpi_card("Forecast Spend", forecast_spend, None, fmt_type="currency", higher_is_better=False, currency_symbol=currency_sym, comparison_label=comp_lbl)
with b_row3[1]:
    render_kpi_card("ROAS", roas, prev_roas, fmt_type="multiplier", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)
with b_row3[2]:
    render_kpi_card("ROI", roi, prev_roi, fmt_type="percentage", higher_is_better=True, currency_symbol=currency_sym, comparison_label=comp_lbl, incomplete=is_inc)


st.divider()

# ============================================================
# CHARTS: Budget vs Actual, Planned vs Actual Pacing, ROAS & ROI by Campaign
# ============================================================

st.subheader("📊 Budget Allocation & Pacing Charts")

bc1, bc2, bc3 = st.columns([1.3, 1.1, 1.1])

with bc1:
    curr_campaigns_budget = curr_campaigns.copy()
    curr_campaigns_budget["approved_budget"] = convert_currency(curr_campaigns_budget["approved_budget"])
    curr_campaigns_budget["spend"] = convert_currency(curr_campaigns_budget["spend"])
    fig_budget = px.bar(
        curr_campaigns_budget,
        x="campaign_name",
        y=["approved_budget", "spend"],
        barmode="group",
        title=f"Approved Budget vs Actual Spend by Campaign ({currency_sym})",
        color_discrete_map={"approved_budget": "#4F8CFF", "spend": "#FF4D5A"},
        labels={"value": f"Amount ({currency_sym})", "variable": "Metric"}
    )
    fig_budget.update_layout(yaxis_tickprefix=currency_sym)
    apply_chart_theme(fig_budget, title=f"Approved Budget vs Actual Spend by Campaign ({currency_sym})", height=320)
    st.plotly_chart(fig_budget, use_container_width=True)

with bc2:
    budget_by_plat = curr_campaigns.groupby("platform")["approved_budget"].sum().reset_index()
    budget_by_plat_disp = budget_by_plat.copy()
    budget_by_plat_disp["approved_budget"] = convert_currency(budget_by_plat_disp["approved_budget"])
    fig_budget_pie = px.pie(
        budget_by_plat_disp,
        values="approved_budget",
        names="platform",
        title=f"Approved Budget by Platform ({currency_sym})",
        hole=0.45,
        color="platform",
        color_discrete_sequence=["#38BDF8", "#FF4D5A", "#10B981"]
    )
    apply_chart_theme(fig_budget_pie, title=f"Approved Budget by Platform ({currency_sym})", height=320)
    st.plotly_chart(fig_budget_pie, use_container_width=True)

with bc3:
    fig_pacing = px.bar(
        curr_campaigns,
        x="campaign_name",
        y="budget_utilization",
        title="Budget Utilization (%) by Campaign",
        text_auto=".1f",
        color="budget_utilization",
        color_continuous_scale=["#22C55E", "#F59E0B", "#EF4444"]
    )
    apply_chart_theme(fig_pacing, title="Budget Utilization (%) by Campaign", height=320)
    st.plotly_chart(fig_pacing, use_container_width=True)

rc1, rc2 = st.columns(2)

with rc1:
    fig_roas = px.bar(
        curr_campaigns,
        x="campaign_name",
        y=["roas", "target_ROAS"],
        barmode="group",
        title="Actual ROAS vs Target ROAS by Campaign",
        color_discrete_map={"roas": "#22C55E", "target_ROAS": "#94A3B8"}
    )
    apply_chart_theme(fig_roas, title="Actual ROAS vs Target ROAS by Campaign", height=320)
    st.plotly_chart(fig_roas, use_container_width=True)

with rc2:
    fig_roi = px.bar(
        curr_campaigns,
        x="campaign_name",
        y="roi",
        title="ROI (%) by Campaign",
        text_auto=".1f",
        color="roi",
        color_continuous_scale=["#EF4444", "#4F8CFF", "#22C55E"]
    )
    apply_chart_theme(fig_roi, title="ROI (%) by Campaign", height=320)
    st.plotly_chart(fig_roi, use_container_width=True)

st.divider()

# ============================================================
# DETAILED BUDGET TABLE
# ============================================================

st.subheader("📋 Campaign Budget Performance Table")

curr_campaigns_table = curr_campaigns.copy()
curr_campaigns_table["approved_budget"] = convert_currency(curr_campaigns_table["approved_budget"])
curr_campaigns_table["spend"] = convert_currency(curr_campaigns_table["spend"])
curr_campaigns_table["revenue"] = convert_currency(curr_campaigns_table["revenue"])

st.dataframe(
    curr_campaigns_table[
        [
            "campaign_id",
            "platform",
            "campaign_name",
            "approved_budget",
            "spend",
            "budget_utilization",
            "revenue",
            "conversions",
            "roas",
            "target_ROAS",
            "roi"
        ]
    ].style.format({
        "approved_budget": f"{currency_sym}{{:,.2f}}",
        "spend": f"{currency_sym}{{:,.2f}}",
        "budget_utilization": "{:.1f}%",
        "revenue": f"{currency_sym}{{:,.2f}}",
        "conversions": "{:,.0f}",
        "roas": "{:.2f}x",
        "target_ROAS": "{:.2f}x",
        "roi": "{:,.1f}%"
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# ============================================================
# AI MARKETING ASSISTANT
# ============================================================

render_ai_assistant("Budget and ROI", active_filters=filters)