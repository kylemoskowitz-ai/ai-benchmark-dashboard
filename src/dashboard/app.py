"""Main Streamlit dashboard application."""

import streamlit as st
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import ensure_dirs
from src.db.connection import init_database, get_db_path, get_last_update

# Page configuration
st.set_page_config(
    page_title="AI Benchmark Progress",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean, scientific look
st.markdown("""
<style>
    /* Clean, minimal styling */
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
    }

    /* Reduce padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Trust tier badges */
    .trust-a { color: #1a7f37; font-weight: bold; }
    .trust-b { color: #9a6700; font-weight: bold; }
    .trust-c { color: #6e7781; font-weight: bold; }

    /* Disclaimer styling */
    .disclaimer {
        background-color: #fff8e6;
        border-left: 4px solid #f0ad4e;
        padding: 1rem;
        margin: 1rem 0;
        font-size: 0.9rem;
    }

    /* Footer */
    .footer {
        font-size: 0.8rem;
        color: #6e7781;
        text-align: center;
        padding: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_db():
    """Ensure database is initialized."""
    ensure_dirs()
    db_path = get_db_path()
    if not db_path.exists():
        with st.spinner("Initializing database..."):
            init_database()
            # Load initial data
            from scripts.update_data import run_update
            run_update(dry_run=False)


def main():
    """Main dashboard application."""
    # Initialize
    initialize_db()

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

        # Last update info
        last_update = get_last_update()
        if last_update:
            st.caption(f"Last update: {last_update.strftime('%Y-%m-%d %H:%M')} UTC")
        else:
            st.caption("No data loaded yet")

        # Quick filters
        st.subheader("Quick Filters")

        frontier_only = st.checkbox("Frontier only", value=False, help="Show only best-performing models per date")
        official_only = st.checkbox("Official sources only", value=False, help="Show only Tier A data")

        # Store in session state
        st.session_state["frontier_only"] = frontier_only
        st.session_state["official_only"] = official_only

    # Route to page
    if "Overview" in page:
        from src.dashboard.pages.overview import render_overview
        render_overview()
    elif "Benchmark Explorer" in page:
        from src.dashboard.pages.benchmark_explorer import render_benchmark_explorer
        render_benchmark_explorer()
    elif "Model Explorer" in page:
        from src.dashboard.pages.model_explorer import render_model_explorer
        render_model_explorer()
    elif "Projections" in page:
        from src.dashboard.pages.projections import render_projections
        render_projections()
    elif "Data Quality" in page:
        from src.dashboard.pages.data_quality import render_data_quality
        render_data_quality()

    # Footer
    st.markdown("""
    <div class="footer">
        <p>AI Benchmark Progress Dashboard | Data-quality-first tracking</p>
        <p>Every data point has full provenance. Missing data is explicit, not interpolated.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
