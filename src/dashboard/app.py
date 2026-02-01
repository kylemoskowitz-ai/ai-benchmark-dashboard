"""Main Streamlit dashboard application - Redesigned."""

import os
import streamlit as st
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="AI Benchmark Tracker",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Academic minimalist CSS
st.markdown("""
<style>
    /* Import serif font */
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600&family=JetBrains+Mono&display=swap');

    /* Base layout */
    .block-container {
        padding: 1.5rem 3rem 2rem;
        max-width: 1200px;
    }

    /* Hide default sidebar */
    section[data-testid="stSidebar"] {
        display: none;
    }

    /* Typography */
    h1, h2, h3 {
        font-family: 'Source Serif 4', Georgia, serif !important;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: #1A1A1A;
    }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.5rem; margin-top: 2rem; }
    h3 { font-size: 1.15rem; margin-top: 1.5rem; }

    p, li, label, .stMarkdown {
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #333;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 1rem 1.25rem;
        border-radius: 8px;
        border: 1px solid #E8E8E8;
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.75rem;
        font-weight: 600;
        color: #1A1A1A;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.75rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Cards */
    .benchmark-card {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-radius: 8px;
        padding: 1.25rem;
        transition: box-shadow 0.2s;
    }
    .benchmark-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .benchmark-card h4 {
        font-family: 'Source Serif 4', serif;
        font-size: 1rem;
        margin: 0 0 0.5rem 0;
        color: #1A1A1A;
    }
    .benchmark-card .score {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.5rem;
        font-weight: 600;
        color: #4C5C78;
    }
    .benchmark-card .model {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .benchmark-card .date {
        font-size: 0.75rem;
        color: #999;
    }

    /* Tables */
    .stDataFrame {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem;
    }
    .stDataFrame th {
        background: #F8F9FA !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.05em;
    }

    /* Charts */
    .stPlotlyChart {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-radius: 8px;
        padding: 1rem;
    }

    /* Buttons */
    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        background: #FFFFFF;
        border: 1px solid #DDD;
        color: #333;
        font-size: 0.85rem;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #F5F5F5;
        border-color: #BBB;
    }
    .stDownloadButton > button {
        background: #FFFFFF;
        border: 1px solid #DDD;
    }

    /* Select boxes */
    .stSelectbox label, .stMultiSelect label {
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid #E8E8E8;
        margin: 2rem 0;
    }

    /* Footer */
    .footer {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        color: #888;
        text-align: center;
        padding: 2rem 0 1rem;
        margin-top: 3rem;
        border-top: 1px solid #E8E8E8;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 1px solid #E8E8E8;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #666;
        padding: 0.75rem 0;
        border-bottom: 2px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #1A1A1A;
        border-bottom-color: #4C5C78;
    }
</style>
""", unsafe_allow_html=True)


def get_database_path() -> Path:
    """Get path to database file."""
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return PROJECT_ROOT / "data" / "benchmark.duckdb"


def main():
    """Main dashboard application."""
    db_path = get_database_path()

    if not db_path.exists():
        st.error(f"Database not found at {db_path}")
        st.info("Run `make init-db` to initialize the database.")
        return

    # Header with navigation
    col_logo, col_nav, col_meta = st.columns([2, 6, 2])

    with col_logo:
        st.markdown("### ◈ AI Benchmark Tracker")

    with col_meta:
        try:
            from src.db.connection import get_last_update
            last_update = get_last_update()
            if last_update:
                st.caption(f"Updated {last_update.strftime('%b %d, %Y')}")
        except Exception:
            pass

    # Tab-based navigation
    tabs = st.tabs(["Progress", "Explorer", "Projections", "Admin"])

    # Import pages - these will be created in subsequent tasks
    # For now, show placeholder content
    try:
        with tabs[0]:
            try:
                from src.dashboard.pages.progress import render_progress
                render_progress()
            except ImportError:
                st.info("Progress page coming soon...")
        with tabs[1]:
            try:
                from src.dashboard.pages.explorer import render_explorer
                render_explorer()
            except ImportError:
                st.info("Explorer page coming soon...")
        with tabs[2]:
            try:
                from src.dashboard.pages.projections import render_projections
                render_projections()
            except ImportError:
                st.info("Projections page coming soon...")
        with tabs[3]:
            try:
                from src.dashboard.pages.admin import render_admin
                render_admin()
            except ImportError:
                st.info("Admin page coming soon...")
    except Exception as e:
        st.error("Error loading page")
        with st.expander("Details"):
            st.exception(e)

    # Footer
    st.markdown("""
    <div class="footer">
        Every data point has a source · Missing data is explicit · <a href="https://github.com/kylemoskowitz-ai/ai-benchmark-dashboard" style="color:#666;">GitHub</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
