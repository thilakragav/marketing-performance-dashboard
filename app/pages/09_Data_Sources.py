import streamlit as st
import pandas as pd
import plotly.express as px
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from app.components.theme import apply_enterprise_theme
from app.components.sidebar import render_global_sidebar
from app.components.header import render_global_header
from app.components.charts import apply_chart_theme
from app.services.data_sources.manager import get_data_source_manager

st.set_page_config(
    page_title="Data Sources & Freshness",
    page_icon="🔄",
    layout="wide"
)

apply_enterprise_theme()
render_global_sidebar()

from app.services.database import get_database_engine

@st.cache_resource
def get_engine():
    return get_database_engine()

engine = get_engine()

render_global_header(
    title="Data Sources & Pipeline Freshness",
    description="Live API connectors, static CSV fallbacks, database sync states and freshness telemetry",
    icon="🔄",
    engine=engine
)

mgr = get_data_source_manager()
sources = mgr.get_source_statuses(engine=engine)

# Top metric summary
total_sources = len(sources)
active_sources = sum(1 for s in sources if s["status"] == "Fresh")
total_records = sum(s["record_count"] for s in sources)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Connected Sources", f"{total_sources}")
with c2:
    st.metric("Healthy / Fresh Sources", f"{active_sources} / {total_sources}", delta="100% Operational")
with c3:
    st.metric("Total Ingested Records", f"{total_records:,}")
with c4:
    st.metric("System Refresh Cadence", "Every 24h", delta="Next: 21:30 IST", delta_color="off")

st.markdown("### 🔌 Source Connectors & Live Telemetry")

cols = st.columns(len(sources))

for i, src in enumerate(sources):
    with cols[i]:
        status_color = "#10b981" if src["status"] == "Fresh" else "#ef4444"
        badge_type = "LIVE API" if src["connection_type"] == "Live API" else "POSTGRESQL / CSV"
        badge_bg = "rgba(59, 130, 246, 0.15)" if src["connection_type"] == "Live API" else "rgba(148, 163, 184, 0.15)"
        badge_color = "#60a5fa" if src["connection_type"] == "Live API" else "#94a3b8"

        card_html = f"""
        <div class="kpi-card" style="min-height: 240px;">
            <div class="kpi-header">
                <span style="font-weight: 700; color: #f8fafc; font-size: 0.95rem;">{src['source']}</span>
                <span style="font-size: 0.72rem; color: {status_color}; font-weight: 600;">● {src['status']}</span>
            </div>
            <div style="margin: 8px 0;">
                <span style="background: {badge_bg}; color: {badge_color}; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em;">
                    {badge_type}
                </span>
            </div>
            <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 12px;">
                Records: <strong style="color: #f8fafc;">{src['record_count']:,}</strong>
            </div>
            <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 4px;">
                Date Range: <span style="color: #cbd5e1;">{src['date_range']}</span>
            </div>
            <div style="font-size: 0.75rem; color: #64748b; margin-top: 8px; border-top: 1px solid #27354f; padding-top: 6px;">
                Last Refresh:<br><span style="color: #94a3b8;">{src['last_refresh']}</span>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

st.divider()

st.subheader("📊 Ingestion Volume Distribution")
df_sources = pd.DataFrame(sources)

fig_src_pie = px.pie(
    df_sources,
    values="record_count",
    names="source",
    title="Data Volume Share by Connector (Total Records Ingested)",
    hole=0.45,
    color_discrete_sequence=["#38BDF8", "#FF4D5A", "#10B981", "#F59E0B", "#818CF8"]
)
apply_chart_theme(fig_src_pie, title="Data Volume Share by Connector (Total Records Ingested)", height=320)
st.plotly_chart(fig_src_pie, use_container_width=True)

st.subheader("📋 Ingestion Telemetry Table")
st.dataframe(
    df_sources,
    use_container_width=True,
    hide_index=True
)

st.divider()

st.subheader("⚙️ Live Feed Configuration & Secrets")
st.info(
    """
    **Production Credentials Guidance:**
    - Live API feeds attempt to authenticate using environment variables or Streamlit secrets (`.streamlit/secrets.toml`).
    - Configured keys: `GA4_PROPERTY_ID`, `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_DEVELOPER_TOKEN`, `LINKEDIN_ACCESS_TOKEN`, `META_ACCESS_TOKEN`, `GSC_PROPERTY`.
    - If credentials are not supplied, the platform automatically and gracefully falls back to the high-integrity PostgreSQL / CSV repository without runtime interruption.
    """
)
