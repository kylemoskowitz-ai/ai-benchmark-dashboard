"""Main Streamlit dashboard application."""

import os
import streamlit as st
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="AI Benchmark Progress",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean, modern look
st.markdown("""
<style>
    /* Metric cards */
    .stMetric {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        padding: 1rem;
        border-radius: 0.75rem;
        border: 1px solid #e9ecef;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stMetric:hover {
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }

    /* Main container */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Trust tier colors */
    .trust-a { color: #1a7f37; font-weight: 600; }
    .trust-b { color: #9a6700; font-weight: 600; }
    .trust-c { color: #6e7781; font-weight: 600; }

    /* Disclaimer box */
    .disclaimer {
        background-color: #fffbeb;
        border-left: 4px solid #f59e0b;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
        font-size: 0.9rem;
        border-radius: 0 0.5rem 0.5rem 0;
    }

    /* Footer */
    .footer {
        font-size: 0.8rem;
        color: #6b7280;
        text-align: center;
        padding: 2rem 0 1rem 0;
        border-top: 1px solid #e5e7eb;
        margin-top: 2rem;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #fafbfc;
    }
    section[data-testid="stSidebar"] .stRadio > label {
        font-weight: 500;
    }

    /* Table improvements */
    .stDataFrame {
        border-radius: 0.5rem;
        overflow: hidden;
    }

    /* Chart containers */
    .stPlotlyChart {
        border-radius: 0.5rem;
        overflow: hidden;
    }

    /* Download button styling */
    .stDownloadButton > button {
        background-color: #f8f9fa;
        border: 1px solid #d1d5db;
        color: #374151;
    }
    .stDownloadButton > button:hover {
        background-color: #e5e7eb;
        border-color: #9ca3af;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        font-weight: 500;
        color: #374151;
    }

    /* Divider */
    hr {
        border-color: #e5e7eb;
        margin: 1.5rem 0;
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
    # Check database exists
    db_path = get_database_path()
    
    if not db_path.exists():
        st.error(f"Database not found at {db_path}")
        st.info("Please run `make init-db` to initialize the database.")
        return

    # Sidebar
    with st.sidebar:
        st.title("📊 AI Benchmark Progress")
        st.caption("Data-quality-first tracking")

        st.divider()

        # Navigation
        page = st.radio(
            "Navigation",
            [
                "🏠 Overview",
                "📈 Benchmark Explorer",
                "🤖 Model Explorer",
                "🔮 Projections",
                "✅ Data Quality",
            ],
            label_visibility="collapsed",
        )

        st.divider()

        # Quick filters
        st.subheader("Filters")

        official_only = st.checkbox(
            "Official sources only",
            value=False,
            help="Show only Tier A (official) data sources"
        )
        st.session_state["official_only"] = official_only

        st.divider()

        # Last update info
        try:
            from src.db.connection import get_last_update
            last_update = get_last_update()
            if last_update:
                st.caption(f"Updated: {last_update.strftime('%b %d, %Y')}")
        except Exception:
            pass

    # Import page modules at top level for better error handling
    from src.dashboard.pages.overview import render_overview
    from src.dashboard.pages.benchmark_explorer import render_benchmark_explorer
    from src.dashboard.pages.model_explorer import render_model_explorer
    from src.dashboard.pages.projections import render_projections
    from src.dashboard.pages.data_quality import render_data_quality

    # Route to page
    try:
        if "Overview" in page:
            render_overview()
        elif "Benchmark Explorer" in page:
            render_benchmark_explorer()
        elif "Model Explorer" in page:
            render_model_explorer()
        elif "Projections" in page:
            render_projections()
        elif "Data Quality" in page:
            render_data_quality()
    except Exception as e:
        st.error("Something went wrong loading this page.")
        with st.expander("Error details"):
            st.code(str(e))

    # Footer
    st.markdown("""
    <div class="footer">
        <p>AI Benchmark Progress Dashboard | Data-quality-first tracking</p>
        <p>Every data point has full provenance. Missing data is explicit, not interpolated.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
