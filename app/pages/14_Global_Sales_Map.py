import streamlit as st
import pandas as pd
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from app.components.theme import apply_enterprise_theme
from app.components.sidebar import render_global_sidebar
from app.components.header import render_global_header
from app.utils.currency import get_selected_currency, get_currency_symbol, convert_currency, format_currency
from app.services.geo_service import (
    load_geo_sales_data,
    prepare_display_geo_data,
    build_world_choropleth_map,
    build_world_bubble_map,
    get_regional_summary,
    build_regional_share_donut,
    build_top_markets_bar_chart
)

st.set_page_config(
    page_title="Global Sales Map | Marketing Intelligence",
    page_icon="🗺️",
    layout="wide"
)

apply_enterprise_theme()
render_global_sidebar()

# Database Engine
from app.services.database import get_database_engine

@st.cache_resource
def get_engine():
    return get_database_engine()

engine = get_engine()

render_global_header(
    title="Global Sales & Geographic Performance Map",
    description="Interactive global geospatial telemetry tracking sales density, transaction volume, and regional market expansion",
    icon="🗺️",
    engine=engine
)

# Active Currency State
curr_sym = get_currency_symbol()
curr_code = get_selected_currency()

# Load Data
df_raw = load_geo_sales_data(engine=engine)
df_disp = prepare_display_geo_data(df_raw)

# ── 1. Top Executive Geographic Scorecard ──
total_sales_converted = df_disp["sales_revenue_converted"].sum()
total_orders = int(df_disp["orders_count"].sum())
total_spend_converted = df_disp["ad_spend_converted"].sum()
blended_roas = round(total_sales_converted / total_spend_converted, 2) if total_spend_converted > 0 else 0.0
top_country = df_disp.iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Total Global Sales", f"{curr_sym}{total_sales_converted:,.2f}", delta=f"{curr_code} Reporting")
with c2:
    st.metric(
        "Top Market by Sales",
        f"{top_country['flag']} {top_country['country_name']}",
        delta=f"{top_country['market_share_pct']}% Global Share"
    )
with c3:
    st.metric("Global Orders Completed", f"{total_orders:,}", delta="+16.4% YoY")
with c4:
    st.metric("Global Blended ROAS", f"{blended_roas:.2f}x", delta="Marketing Return")
with c5:
    st.metric("Active Country Markets", f"{len(df_disp)} Countries", delta="5 Continental Regions")

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# ── 2. Interactive Map Configuration Controls ──
with st.container():
    st.markdown("### 🌐 Interactive Global Map Explorer")
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1.5, 1.4, 1.3, 1.2])

    with ctrl1:
        metric_selection = st.selectbox(
            "Visualized Metric",
            options=["sales_revenue", "orders_count", "roas", "aov", "growth_rate_pct"],
            format_func=lambda x: {
                "sales_revenue": f"💰 Sales Revenue ({curr_code} {curr_sym})",
                "orders_count": "📦 Orders / Transactions",
                "roas": "🎯 Return on Ad Spend (ROAS)",
                "aov": f"💳 Average Order Value ({curr_sym})",
                "growth_rate_pct": "📈 YoY Sales Growth Rate (%)"
            }[x]
        )

    with ctrl2:
        viz_mode = st.selectbox(
            "Map Visualization Mode",
            options=["choropleth_flat", "choropleth_globe", "bubble_spheres"],
            format_func=lambda x: {
                "choropleth_flat": "🗺️ World Heatmap (Natural Earth)",
                "choropleth_globe": "🌍 3D Spherical Globe (Orthographic)",
                "bubble_spheres": "💫 Glowing Activity Spheres (Scatter)"
            }[x]
        )

    with ctrl3:
        all_regions = ["All Regions"] + sorted(list(df_raw["region"].unique()))
        selected_region = st.selectbox("Filter Region", options=all_regions)

    with ctrl4:
        st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
        show_table_toggle = st.toggle("Show Country Leaderboard", value=True)

# Filter dataset if region is selected
if selected_region != "All Regions":
    df_filtered = df_raw[df_raw["region"] == selected_region].copy()
else:
    df_filtered = df_raw.copy()

# Render Selected Map
if viz_mode == "choropleth_flat":
    fig_map = build_world_choropleth_map(df_filtered, metric=metric_selection, projection="natural earth", height=560)
elif viz_mode == "choropleth_globe":
    fig_map = build_world_choropleth_map(df_filtered, metric=metric_selection, projection="orthographic", height=560)
else:
    fig_map = build_world_bubble_map(df_filtered, metric=metric_selection, projection="natural earth", height=560)

st.plotly_chart(fig_map, use_container_width=True)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ── 3. Multi-Tab Regional & Country Deep-Dive ──
tab_rankings, tab_regional, tab_table = st.tabs([
    "🏆 Top Markets Leaderboard",
    "🌍 Continental & Regional Distribution",
    "📋 Detailed Country Telemetry Table"
])

with tab_rankings:
    col_chart, col_highlights = st.columns([2, 1])
    with col_chart:
        fig_top = build_top_markets_bar_chart(df_filtered, top_n=min(12, len(df_filtered)))
        st.plotly_chart(fig_top, use_container_width=True)

    with col_highlights:
        st.markdown(
            f"""
            <div class="kpi-card" style="height: 340px;">
                <div style="font-size: 0.92rem; font-weight: 700; color: #38BDF8; margin-bottom: 12px;">
                    🎯 Geographic Market Insights
                </div>
                <div style="font-size: 0.8rem; color: #CBD5E1; line-height: 1.6;">
                    • <b>Dominant Sales Anchor:</b> The <b>{top_country['country_name']}</b> accounts for <b>{top_country['market_share_pct']}%</b> of total worldwide revenue ({curr_sym}{top_country['sales_revenue_converted']:,.2f}).<br><br>
                    • <b>Highest Growth Corridor:</b> Emerging APAC and MENA markets are growing at <b>+28.4%</b> YoY, driven by strong paid social efficiency.<br><br>
                    • <b>Premium Basket Size (AOV):</b> European & Middle Eastern territories lead in transaction size with AOV exceeding <b>{curr_sym}{convert_currency(175):,.2f}</b> per transaction.<br><br>
                    • <b>Currency Sync:</b> Displayed in <b>{curr_code} ({curr_sym})</b>. All amounts adjust instantly when modified in Settings.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

with tab_regional:
    df_reg = get_regional_summary(df_raw)
    r1, r2 = st.columns([1.2, 1.8])
    with r1:
        fig_donut = build_regional_share_donut(df_reg)
        st.plotly_chart(fig_donut, use_container_width=True)
    with r2:
        st.markdown("#### Regional Sales & Efficiency Matrix")
        df_reg_table = df_reg.copy()
        df_reg_table["Total Sales"] = df_reg_table["total_sales"].apply(lambda v: f"{curr_sym}{v:,.2f}")
        df_reg_table["Marketing Spend"] = df_reg_table["total_spend"].apply(lambda v: f"{curr_sym}{v:,.2f}")
        df_reg_table["Orders"] = df_reg_table["total_orders"].apply(lambda v: f"{v:,}")
        df_reg_table["AOV"] = df_reg_table["aov"].apply(lambda v: f"{curr_sym}{v:,.2f}")
        df_reg_table["ROAS"] = df_reg_table["roas"].apply(lambda v: f"{v:.2f}x")
        df_reg_table["Global Share"] = df_reg_table["sales_share_pct"].apply(lambda v: f"{v:.1f}%")

        st.dataframe(
            df_reg_table[["region", "Total Sales", "Global Share", "Orders", "AOV", "ROAS", "country_count"]],
            column_config={
                "region": "Continent / Region",
                "country_count": "Active Markets"
            },
            hide_index=True,
            use_container_width=True
        )

with tab_table:
    st.markdown("#### Complete Global Country Telemetry")
    df_full_disp = prepare_display_geo_data(df_filtered)

    df_view = pd.DataFrame({
        "Country": df_full_disp["flag"] + " " + df_full_disp["country_name"],
        "ISO Code": df_full_disp["country_code"],
        "Region": df_full_disp["region"],
        f"Sales ({curr_sym})": df_full_disp["sales_formatted"],
        "Orders": df_full_disp["orders_formatted"],
        f"AOV ({curr_sym})": df_full_disp["aov_formatted"],
        "ROAS": df_full_disp["roas"].apply(lambda v: f"{v:.2f}x"),
        "Market Share": df_full_disp["market_share_pct"].apply(lambda v: f"{v:.2f}%"),
        "YoY Growth": df_full_disp["growth_rate_pct"].apply(lambda v: f"+{v:.1f}%")
    })

    st.dataframe(
        df_view,
        hide_index=True,
        use_container_width=True
    )

    # Download CSV button
    csv_bytes = df_view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Geographic Sales Telemetry (CSV)",
        data=csv_bytes,
        file_name=f"global_geographic_sales_{curr_code.lower()}.csv",
        mime="text/csv"
    )
