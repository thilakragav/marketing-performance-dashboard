import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import plotly.express as px

from app.components.theme import apply_enterprise_theme
from app.components.sidebar import render_global_sidebar
from app.components.header import render_global_header
from app.components.kpi_card import render_kpi_card
from app.components.filter_bar import render_filter_bar
from app.components.ai_assistant import render_ai_assistant

from app.components.charts import apply_chart_theme
from app.components.badges import render_status_badge
from app.utils.currency import get_currency_symbol, convert_currency, format_currency
from app.services.geo_service import load_geo_sales_data, build_world_choropleth_map

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Marketing Intelligence",
    page_icon="📊",
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

# ============================================================
# HEADER
# ============================================================

render_global_header(
    title="Marketing Intelligence",
    description="One place to understand your marketing performance.",
    icon="📊",
    engine=engine
)

if not engine:
    st.error("Unable to connect to PostgreSQL. Please check database credentials in .streamlit/secrets.toml.")
    st.stop()

# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=300)
def load_paid_media_all():
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
        ORDER BY date
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    df["date"] = pd.to_datetime(df["date"])
    return df

try:
    df_paid = load_paid_media_all()
except Exception as error:
    st.error("Unable to load data from PostgreSQL.")
    st.caption(f"Error: {str(error)}")
    st.stop()

min_date = df_paid["date"].min().date()
max_date = df_paid["date"].max().date()
all_channels = sorted(df_paid["platform"].unique().tolist())

# ============================================================
# GLOBAL FILTER BAR WITH DATE COMPARISON
# ============================================================

filters = render_filter_bar(
    min_date=min_date,
    max_date=max_date,
    channel_options=all_channels,
    key_prefix="home"
)

# Filter current period
curr_df = df_paid[
    (df_paid["date"] >= filters["start_date"])
    & (df_paid["date"] <= filters["end_date"])
    & (df_paid["platform"].isin(filters["selected_channels"]))
]

# Filter previous comparison period
prev_df = df_paid[
    (df_paid["date"] >= filters["comp_start"])
    & (df_paid["date"] <= filters["comp_end"])
    & (df_paid["platform"].isin(filters["selected_channels"]))
]

if curr_df.empty:
    st.warning("No data is available for the selected filters.")
    st.stop()

# ============================================================
# KPI COMPUTATIONS (CURRENT VS PREVIOUS)
# ============================================================

curr_spend = curr_df["spend"].sum()
prev_spend = prev_df["spend"].sum() if not prev_df.empty else 0.0

curr_rev = curr_df["conversion_value"].sum()
prev_rev = prev_df["conversion_value"].sum() if not prev_df.empty else 0.0

curr_conv = curr_df["conversions"].sum()
prev_conv = prev_df["conversions"].sum() if not prev_df.empty else 0.0

curr_leads = curr_df["leads"].sum()
prev_leads = prev_df["leads"].sum() if not prev_df.empty else 0.0

curr_roas = (curr_rev / curr_spend) if curr_spend > 0 else 0.0
prev_roas = (prev_rev / prev_spend) if prev_spend > 0 else 0.0

curr_roi = ((curr_rev - curr_spend) / curr_spend * 100) if curr_spend > 0 else 0.0
prev_roi = ((prev_rev - prev_spend) / prev_spend * 100) if prev_spend > 0 else 0.0

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

# ============================================================
# EXECUTIVE SCORECARD (2 ROWS OF 3 CARDS)
# ============================================================

st.markdown(
    """
    <div class="section-header-enhanced">
        <span class="section-icon">📊</span>
        <span class="section-title">Executive Scorecard</span>
        <span class="section-line"></span>
        <span class="section-badge">Live</span>
    </div>
    """,
    unsafe_allow_html=True
)

row1_col1, row1_col2, row1_col3 = st.columns(3)

with row1_col1:
    render_kpi_card(
        title="Spend",
        current_val=curr_spend,
        previous_val=prev_spend,
        fmt_type="currency",
        higher_is_better=False,
        currency_symbol=currency_sym,
        comparison_label=comp_lbl,
        incomplete=is_inc
    )

with row1_col2:
    render_kpi_card(
        title="Revenue",
        current_val=curr_rev,
        previous_val=prev_rev,
        fmt_type="currency",
        higher_is_better=True,
        currency_symbol=currency_sym,
        comparison_label=comp_lbl,
        incomplete=is_inc
    )

with row1_col3:
    render_kpi_card(
        title="Conversions",
        current_val=curr_conv,
        previous_val=prev_conv,
        fmt_type="integer",
        higher_is_better=True,
        currency_symbol=currency_sym,
        comparison_label=comp_lbl,
        incomplete=is_inc
    )

row2_col1, row2_col2, row2_col3 = st.columns(3)

with row2_col1:
    render_kpi_card(
        title="ROAS",
        current_val=curr_roas,
        previous_val=prev_roas,
        fmt_type="multiplier",
        higher_is_better=True,
        currency_symbol=currency_sym,
        comparison_label=comp_lbl,
        incomplete=is_inc
    )

with row2_col2:
    render_kpi_card(
        title="ROI",
        current_val=curr_roi,
        previous_val=prev_roi,
        fmt_type="percentage",
        higher_is_better=True,
        currency_symbol=currency_sym,
        comparison_label=comp_lbl,
        incomplete=is_inc
    )

with row2_col3:
    render_kpi_card(
        title="CPA",
        current_val=curr_cpa,
        previous_val=prev_cpa,
        fmt_type="currency_precise",
        higher_is_better=False,
        currency_symbol=currency_sym,
        comparison_label=comp_lbl,
        incomplete=is_inc
    )

st.divider()

# ============================================================
# CHANNEL PERFORMANCE SUMMARY & CHARTS
# ============================================================

channel_summary = (
    curr_df.groupby("platform")
    .agg(
        spend=("spend", "sum"),
        revenue=("conversion_value", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        leads=("leads", "sum"),
        conversions=("conversions", "sum"),
    )
    .reset_index()
)

channel_summary["roas"] = (channel_summary["revenue"] / channel_summary["spend"]).round(2)
channel_summary["cpa"] = (channel_summary["spend"] / channel_summary["conversions"]).round(2)
channel_summary["ctr"] = (channel_summary["clicks"] / channel_summary["impressions"] * 100).round(2)
channel_summary["roi"] = ((channel_summary["revenue"] - channel_summary["spend"]) / channel_summary["spend"] * 100).round(2)

st.markdown(
    """
    <div class="section-header-enhanced">
        <span class="section-icon">📈</span>
        <span class="section-title">Performance Overview</span>
        <span class="section-line"></span>
        <span class="section-badge">Analytics</span>
    </div>
    """,
    unsafe_allow_html=True
)

ch_col1, ch_col2, ch_col3 = st.columns([1.4, 1.1, 1.1])

with ch_col1:
    daily_trend = (
        curr_df.groupby("date")
        .agg(spend=("spend", "sum"), revenue=("conversion_value", "sum"))
        .reset_index()
    )
    daily_trend_disp = daily_trend.copy()
    daily_trend_disp["spend"] = convert_currency(daily_trend_disp["spend"])
    daily_trend_disp["revenue"] = convert_currency(daily_trend_disp["revenue"])
    fig_daily = px.line(
        daily_trend_disp,
        x="date",
        y=["spend", "revenue"],
        title=f"Daily Spend vs Attributed Revenue ({currency_sym})",
        color_discrete_map={"spend": "#FF4D5A", "revenue": "#22C55E"},
        labels={"value": f"Amount ({currency_sym})", "variable": "Metric"}
    )
    fig_daily.update_layout(yaxis_tickprefix=currency_sym)
    apply_chart_theme(fig_daily, title=f"Daily Spend vs Attributed Revenue ({currency_sym})", height=320)
    st.plotly_chart(fig_daily, use_container_width=True)

with ch_col2:
    channel_summary_pie = channel_summary.copy()
    channel_summary_pie["spend"] = convert_currency(channel_summary_pie["spend"])
    fig_pie = px.pie(
        channel_summary_pie,
        values="spend",
        names="platform",
        title=f"Spend Share by Channel ({currency_sym})",
        hole=0.45,
        color="platform",
        color_discrete_sequence=["#38BDF8", "#FF4D5A", "#10B981"]
    )
    apply_chart_theme(fig_pie, title=f"Spend Share by Channel ({currency_sym})", height=320)
    st.plotly_chart(fig_pie, use_container_width=True)

with ch_col3:
    fig_roas = px.bar(
        channel_summary,
        x="platform",
        y="roas",
        title="ROAS by Channel",
        text_auto=".2f",
        color="platform",
        color_discrete_sequence=["#38BDF8", "#FF4D5A", "#10B981"]
    )
    apply_chart_theme(fig_roas, title="ROAS by Channel", height=320)
    st.plotly_chart(fig_roas, use_container_width=True)

# ============================================================
# CHANNEL MATRIX & EXECUTIVE BRIEFING
# ============================================================

br_col1, br_col2 = st.columns([1.8, 1.2])

with br_col1:
    st.markdown(
        """
        <div class="section-header-enhanced">
            <span class="section-icon">⚡</span>
            <span class="section-title">Channel Performance Breakdown</span>
            <span class="section-line"></span>
        </div>
        """,
        unsafe_allow_html=True
    )
    channel_summary_disp = channel_summary.copy()
    channel_summary_disp["spend"] = convert_currency(channel_summary_disp["spend"])
    channel_summary_disp["revenue"] = convert_currency(channel_summary_disp["revenue"])
    channel_summary_disp["cpa"] = convert_currency(channel_summary_disp["cpa"])
    st.dataframe(
        channel_summary_disp.style.format({
            "spend": f"{currency_sym}{{:,.2f}}",
            "revenue": f"{currency_sym}{{:,.2f}}",
            "impressions": "{:,.0f}",
            "clicks": "{:,.0f}",
            "leads": "{:,.0f}",
            "conversions": "{:,.0f}",
            "roas": "{:.2f}x",
            "cpa": f"{currency_sym}{{:,.2f}}",
            "ctr": "{:.2f}%",
            "roi": "{:,.2f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

with br_col2:
    st.markdown(
        """
        <div class="section-header-enhanced">
            <span class="section-icon">🧠</span>
            <span class="section-title">Intelligence Briefing</span>
            <span class="section-line"></span>
            <span class="section-badge">AI</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    best_roas_row = channel_summary.sort_values("roas", ascending=False).iloc[0] if not channel_summary.empty else None
    top_rev_row = channel_summary.sort_values("revenue", ascending=False).iloc[0] if not channel_summary.empty else None
    best_roas_rev_disp = format_currency(best_roas_row['revenue'] if best_roas_row is not None else 0, decimals=0)
    top_rev_disp = format_currency(top_rev_row['revenue'] if top_rev_row is not None else 0, decimals=0)

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="font-size: 0.88rem; line-height: 1.6; color: #F8FAFC;">
                <div style="margin-bottom: 10px;">
                    <strong style="color: #4F8CFF;">🎯 Top Efficiency Channel:</strong><br/>
                    <span style="color: #94A3B8;">{best_roas_row['platform'] if best_roas_row is not None else 'N/A'} delivers </span>
                    <strong style="color: #22C55E;">{best_roas_row['roas'] if best_roas_row is not None else 0:.2f}x ROAS</strong>
                    <span style="color: #94A3B8;"> with {best_roas_rev_disp} revenue.</span>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong style="color: #4F8CFF;">💰 Primary Revenue Driver:</strong><br/>
                    <span style="color: #94A3B8;">{top_rev_row['platform'] if top_rev_row is not None else 'N/A'} generates </span>
                    <strong style="color: #F8FAFC;">{top_rev_disp}</strong>
                    <span style="color: #94A3B8;"> ({((top_rev_row['revenue'] / curr_rev) * 100) if curr_rev > 0 else 0:.1f}% of portfolio).</span>
                </div>
                <div>
                    <strong style="color: #4F8CFF;">⚡ Portfolio Health:</strong><br/>
                    <span style="color: #94A3B8;">Blended ROAS is </span>
                    <strong style="color: {'#22C55E' if curr_roas >= 2.0 else '#F59E0B'};">{curr_roas:.2f}x</strong>
                    <span style="color: #94A3B8;"> with overall ROI of </span>
                    <strong style="color: {'#22C55E' if curr_roi > 0 else '#EF4444'};">{curr_roi:+.1f}%</strong>.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ============================================================
# GLOBAL GEOGRAPHIC SALES PREVIEW
# ============================================================

st.markdown(
    """
    <div class="section-header-enhanced">
        <span class="section-icon">🗺️</span>
        <span class="section-title">Global Sales & Market Reach</span>
        <span class="section-line"></span>
        <span class="section-badge">Worldwide</span>
    </div>
    """,
    unsafe_allow_html=True
)

geo_df_home = load_geo_sales_data(engine=engine)
fig_geo_home = build_world_choropleth_map(geo_df_home, metric="sales_revenue", projection="natural earth", height=400)
st.plotly_chart(fig_geo_home, use_container_width=True)

h_gcol1, h_gcol2 = st.columns([3, 1])
with h_gcol1:
    top_c = geo_df_home.iloc[0]
    st.markdown(
        f"<div style='font-size: 0.82rem; color: #94A3B8; padding-top: 4px;'>"
        f"Active in <b>32 countries</b> across 5 continental regions. Global sales anchor: <b>{top_c['flag']} {top_c['country_name']}</b> "
        f"({top_c['market_share_pct']}% of global sales, {currency_sym}{convert_currency(top_c['sales_revenue_usd']):,.2f})."
        f"</div>",
        unsafe_allow_html=True
    )
with h_gcol2:
    st.page_link("pages/14_Global_Sales_Map.py", label="Open Global Sales Map 🗺️", icon="🗺️")

# ============================================================
# DATA SOURCE INTEGRATION STATUS
# ============================================================

st.markdown(
    """
    <div class="section-header-enhanced">
        <span class="section-icon">🔗</span>
        <span class="section-title">Data Source Integration Status</span>
        <span class="section-line"></span>
        <span class="section-badge">Pipelines</span>
    </div>
    """,
    unsafe_allow_html=True
)
s1, s2 = st.columns(2)

with s1:
    st.markdown(
        f"""
        <div class="pipeline-status">
            <div class="pipeline-dot pipeline-dot-active"></div>
            <div class="pipeline-info">
                <div class="pipeline-name">Google Ads</div>
                <div class="pipeline-detail">Auto-synced via Pipeline</div>
            </div>
            <div class="pipeline-metric">LIVE</div>
        </div>
        <div class="pipeline-status">
            <div class="pipeline-dot pipeline-dot-active"></div>
            <div class="pipeline-info">
                <div class="pipeline-name">Meta Ads</div>
                <div class="pipeline-detail">Auto-synced via Pipeline</div>
            </div>
            <div class="pipeline-metric">LIVE</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with s2:
    st.markdown(
        f"""
        <div class="pipeline-status">
            <div class="pipeline-dot pipeline-dot-active"></div>
            <div class="pipeline-info">
                <div class="pipeline-name">LinkedIn Ads</div>
                <div class="pipeline-detail">Auto-synced via Pipeline</div>
            </div>
            <div class="pipeline-metric">LIVE</div>
        </div>
        <div class="pipeline-status">
            <div class="pipeline-dot pipeline-dot-active"></div>
            <div class="pipeline-info">
                <div class="pipeline-name">GA4 Analytics</div>
                <div class="pipeline-detail">Daily Session Stream</div>
            </div>
            <div class="pipeline-metric">LIVE</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================
# AI ASSISTANT WITH FILTER AWARENESS
# ============================================================

render_ai_assistant("Marketing Intelligence", active_filters=filters)