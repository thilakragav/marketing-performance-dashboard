"""
Database Service
Provides unified database engine with automatic fallback:
1. Connects to PostgreSQL if configured and reachable.
2. Gracefully falls back to SQLite (data/marketing_dashboard.db) for cloud deployment (Streamlit Community Cloud).
"""
import os
from pathlib import Path
from urllib.parse import quote_plus
import streamlit as st
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SQLITE_DB_PATH = BASE_DIR / "data" / "marketing_dashboard.db"


@st.cache_resource
def get_database_engine():
    """
    Returns a SQLAlchemy Engine instance.
    First tries PostgreSQL using st.secrets or environment variables.
    If PostgreSQL is unreachable or running in the cloud without a local DB,
    automatically uses the embedded SQLite database.
    """
    db_password = ""
    try:
        db_password = st.secrets.get("DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
    except Exception:
        db_password = os.getenv("DB_PASSWORD", "")

    db_user = os.getenv("DB_USER", "postgres")
    try:
        db_user = st.secrets.get("DB_USER", db_user)
    except Exception:
        pass

    db_host = os.getenv("DB_HOST", "127.0.0.1")
    try:
        db_host = st.secrets.get("DB_HOST", db_host)
    except Exception:
        pass

    db_port = os.getenv("DB_PORT", "5432")
    try:
        db_port = st.secrets.get("DB_PORT", db_port)
    except Exception:
        pass

    db_name = os.getenv("DB_NAME", "marketing_dashboard")
    try:
        db_name = st.secrets.get("DB_NAME", db_name)
    except Exception:
        pass

    if db_password and db_host:
        try:
            password = quote_plus(str(db_password))
            database_url = (
                f"postgresql+psycopg2://"
                f"{db_user}:{password}"
                f"@{db_host}:{db_port}/{db_name}"
            )
            engine = create_engine(
                database_url,
                connect_args={"connect_timeout": 2}
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception:
            pass

    # SQLite fallback
    if SQLITE_DB_PATH.exists():
        return create_engine(f"sqlite:///{SQLITE_DB_PATH}")

    return None
