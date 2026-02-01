"""Main Streamlit dashboard application."""

import os
import streamlit as st
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Page configuration
st.set_page_config(
    page_title="AI Benchmark Tracker",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal, clean CSS
st.markdown("""
<style>
    /* Reset and base */
    .block-container {
        padding: 2rem 3rem;
        max-width: 1100px;
    }

    /* Typography */
    h1 {
        font-weight: 600;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem;
    }
    h2, h3 {
        font-weight: 500;
        color: #1a1a1a;
        margin-top: 1.5rem;
    }

    /* Subtle metric styling */
    [data-testid="stMetric"] {
        background: #fafafa;
        padding: 0.75rem 1rem;
        border-radius: 6px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 600;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #f8f8f8;
        border-right: 1px solid #eee;
    }
    section[data-testid="stSidebar"] h1 {
        font-size: 1.1rem;
        color: #333;
    }

    /* Clean dividers */
    hr {
        border: none;
        border-top: 1px solid #e8e8e8;
        margin: 1.5rem 0;
    }

    /* Tables */
    .stDataFrame {
        font-size: 0.85rem;
    }

    /* Buttons */
    .stDownloadButton > button {
        background: white;
        border: 1px solid #ddd;
        color: #333;
        font-size: 0.85rem;
        padding: 0.4rem 0.8rem;
    }
    .stDownloadButton > button:hover {
        background: #f5f5f5;
        border-color: #ccc;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        font-size: 0.9rem;
        font-weight: 500;
    }

    /* Warning/info boxes */
    .disclaimer {
        background: #fffef5;
        border-left: 3px solid #e6b800;
        padding: 0.75rem 1rem;
        margin: 1rem 0;
        font-size: 0.85rem;
        color: #665c00;
    }

    /* Footer */
    .footer {
        font-size: 0.75rem;
        color: #888;
        text-align: center;
        padding: 2rem 0 1rem;
        margin-top: 3rem;
        border-top: 1px solid #eee;
    }

    /* Hide hamburger menu and footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Chart styling */
    .stPlotlyChart {
        background: white;
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

    # Sidebar
    with st.sidebar:
        st.markdown("### ◈ AI Benchmark Tracker")
        st.caption("Data-quality-first tracking")

        st.markdown("---")

        page = st.radio(
            "Navigate",
            [
                "Overview",
                "Benchmark Explorer",
                "Model Explorer",
                "Projections",
                "Data Quality",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")

        # Filters
        st.markdown("##### Filters")
        official_only = st.checkbox(
            "Official sources only",
            value=False,
            help="Tier A sources only"
        )
        st.session_state["official_only"] = official_only

        # Last update
        st.markdown("---")
        try:
            from src.db.connection import get_last_update
            last_update = get_last_update()
            if last_update:
                st.caption(f"Updated {last_update.strftime('%b %d, %Y')}")
        except Exception:
            pass

    # Import pages
    from src.dashboard.pages.overview import render_overview
    from src.dashboard.pages.benchmark_explorer import render_benchmark_explorer
    from src.dashboard.pages.model_explorer import render_model_explorer
    from src.dashboard.pages.projections import render_projections
    from src.dashboard.pages.data_quality import render_data_quality

    # Route to page
    try:
        if page == "Overview":
            render_overview()
        elif page == "Benchmark Explorer":
            render_benchmark_explorer()
        elif page == "Model Explorer":
            render_model_explorer()
        elif page == "Projections":
            render_projections()
        elif page == "Data Quality":
            render_data_quality()
    except Exception as e:
        st.error("Error loading page")
        with st.expander("Details"):
            st.code(str(e))

    # Footer
    st.markdown("""
    <div class="footer">
        AI Benchmark Tracker · Every data point has provenance · Missing data is explicit
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
