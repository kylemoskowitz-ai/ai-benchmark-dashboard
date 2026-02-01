"""Admin page - data management, refresh, and quality monitoring."""

import streamlit as st
import plotly.graph_objects as go
import polars as pl
from pathlib import Path
import json
from datetime import datetime

from src.db.queries import (
    get_all_benchmarks,
    get_all_sources,
    get_data_quality_summary,
    get_unique_providers,
)
from src.db.connection import get_last_update, get_connection

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def render_admin():
    """Render the admin page."""

    st.markdown("## Data Administration")

    # Data refresh section
    st.markdown("### Refresh Data")

    with st.container():
        col1, col2 = st.columns([2, 3])

        with col1:
            if st.button("▶ Refresh All Benchmarks", type="primary", use_container_width=True):
                run_data_refresh()

        with col2:
            last_update = get_last_update()
            if last_update:
                st.success(f"Last refresh: {last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            else:
                st.warning("No successful refresh recorded")

    st.divider()

    # Quality summary
    st.markdown("### Data Quality Overview")

    quality = get_data_quality_summary()

    cols = st.columns(5)
    cols[0].metric("Total Results", f"{quality['total_results']:,}")
    cols[1].metric("Models", f"{quality['total_models']:,}")
    cols[2].metric("Benchmarks", quality['total_benchmarks'])
    cols[3].metric("Missing Scores", f"{quality['missing_scores']:,}")
    cols[4].metric("Coverage", f"{100 - quality['missing_score_pct']:.0f}%")

    st.divider()

    # Trust tier distribution
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Trust Tier Distribution")

        st.markdown("""
        **Tier A** — Official sources (benchmark authors, leaderboards)

        **Tier B** — Semi-official (model provider, Epoch AI)

        **Tier C** — Third-party (community runs, blogs)
        """)

        trust_dist = quality["trust_distribution"]
        if not trust_dist.is_empty():
            for row in trust_dist.iter_rows(named=True):
                tier = row["trust_tier"]
                count = row["count"]
                pct = count / quality["total_results"] * 100 if quality["total_results"] > 0 else 0
                st.caption(f"Tier {tier}: {count:,} ({pct:.1f}%)")

    with col2:
        trust_dist = quality["trust_distribution"]
        if not trust_dist.is_empty():
            fig = go.Figure(data=[go.Pie(
                labels=trust_dist["trust_tier"].to_list(),
                values=trust_dist["count"].to_list(),
                marker=dict(colors=['#4C5C78', '#B8860B', '#888888']),
                hole=0.4,
                textinfo='label+percent',
            )])
            fig.update_layout(
                height=250,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Coverage matrix
    st.markdown("### Coverage Matrix")

    benchmarks = get_all_benchmarks()
    providers = get_unique_providers()

    if not benchmarks.is_empty() and providers:
        try:
            with get_connection(read_only=True) as conn:
                coverage_data = conn.execute("""
                    SELECT
                        b.name as benchmark,
                        m.provider,
                        COUNT(CASE WHEN r.score IS NOT NULL THEN 1 END) as valid
                    FROM benchmarks b
                    CROSS JOIN (SELECT DISTINCT provider FROM models) m
                    LEFT JOIN results r ON r.benchmark_id = b.benchmark_id
                    LEFT JOIN models mo ON r.model_id = mo.model_id AND mo.provider = m.provider
                    GROUP BY b.name, m.provider
                """).pl()

            if not coverage_data.is_empty():
                heatmap_data = coverage_data.pivot(
                    on="provider",
                    index="benchmark",
                    values="valid",
                    aggregate_function="sum",
                ).fill_null(0)

                benchmarks_list = heatmap_data["benchmark"].to_list()
                providers_list = [c for c in heatmap_data.columns if c != "benchmark"]

                if providers_list:
                    matrix = heatmap_data.select(providers_list).to_numpy()

                    fig = go.Figure(data=go.Heatmap(
                        z=matrix,
                        x=providers_list,
                        y=benchmarks_list,
                        colorscale=[[0, '#F5F5F5'], [1, '#4C5C78']],
                        hovertemplate="Benchmark: %{y}<br>Provider: %{x}<br>Results: %{z}<extra></extra>",
                    ))

                    fig.update_layout(
                        height=350,
                        margin=dict(l=20, r=20, t=20, b=20),
                        xaxis=dict(tickangle=-45),
                    )

                    st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.info(f"Coverage matrix not available: {e}")

    st.divider()

    # Data sources
    st.markdown("### Data Sources")

    sources = get_all_sources()

    if not sources.is_empty():
        display_cols = ["source_title", "source_type", "result_count", "retrieved_at"]
        available_cols = [c for c in display_cols if c in sources.columns]

        display_sources = sources.select(available_cols).sort("retrieved_at", descending=True).to_pandas()

        col_mapping = {"source_title": "Source", "source_type": "Type", "result_count": "Results", "retrieved_at": "Retrieved"}
        display_sources = display_sources.rename(columns={k: v for k, v in col_mapping.items() if k in display_sources.columns})

        st.dataframe(display_sources, hide_index=True, use_container_width=True)
    else:
        st.info("No sources recorded.")

    st.divider()

    # Changelog
    st.markdown("### Recent Changes")

    changelog_path = PROJECT_ROOT / "data" / "changelog.jsonl"

    if changelog_path.exists():
        try:
            with open(changelog_path, "r") as f:
                lines = f.readlines()[-20:]

            if lines:
                changelog_entries = []
                for line in reversed(lines):
                    try:
                        entry = json.loads(line.strip())
                        reason = entry.get("reason", "")
                        record_id = entry.get("record_id", "")
                        changelog_entries.append({
                            "Timestamp": entry.get("timestamp", "")[:19] if entry.get("timestamp") else "",
                            "Action": entry.get("action", ""),
                            "Table": entry.get("table", ""),
                            "Record": (record_id[:16] + "...") if len(record_id) > 16 else record_id,
                            "Reason": (reason[:40] + "...") if reason and len(reason) > 40 else reason,
                        })
                    except json.JSONDecodeError:
                        continue

                if changelog_entries:
                    st.dataframe(changelog_entries, hide_index=True, use_container_width=True)
                else:
                    st.info("No changelog entries found.")
            else:
                st.info("Changelog is empty.")
        except Exception:
            st.info("Could not read changelog.")
    else:
        st.info("No changelog file found.")

    st.divider()

    # Export section
    st.markdown("### Export Data")

    col1, col2 = st.columns(2)

    with col1:
        # Export all results as CSV
        try:
            with get_connection(read_only=True) as conn:
                all_results = conn.execute("""
                    SELECT
                        r.*,
                        m.name as model_name,
                        m.provider,
                        b.name as benchmark_name,
                        b.category,
                        s.source_title,
                        s.source_url
                    FROM results r
                    JOIN models m ON r.model_id = m.model_id
                    JOIN benchmarks b ON r.benchmark_id = b.benchmark_id
                    JOIN sources s ON r.source_id = s.source_id
                """).pl()

            if not all_results.is_empty():
                st.download_button(
                    "📥 Export All Data (CSV)",
                    all_results.to_pandas().to_csv(index=False),
                    f"ai_benchmark_data_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True,
                )
        except Exception:
            st.info("No data available for export.")

    with col2:
        # Export database file
        db_path = PROJECT_ROOT / "data" / "benchmark.duckdb"
        if db_path.exists():
            try:
                with open(db_path, "rb") as f:
                    st.download_button(
                        "📥 Export Database (DuckDB)",
                        f.read(),
                        f"benchmark_{datetime.now().strftime('%Y%m%d')}.duckdb",
                        "application/octet-stream",
                        use_container_width=True,
                    )
            except Exception:
                st.info("Database file not accessible.")


def run_data_refresh():
    """Run the data refresh pipeline with live progress."""

    st.markdown("---")
    st.markdown("#### Refresh Progress")

    progress_container = st.empty()
    log_container = st.empty()

    # Get list of ingestors
    try:
        from src.ingestors import INGESTORS
    except ImportError:
        st.error("Could not import ingestors. Check your installation.")
        return

    total = len(INGESTORS)
    if total == 0:
        st.warning("No ingestors configured.")
        return

    completed = 0
    results_log = []

    for benchmark_id, ingestor_cls in INGESTORS.items():
        # Update progress
        progress_container.progress(completed / total, text=f"Processing {benchmark_id}...")

        try:
            ingestor = ingestor_cls()
            result = ingestor.run(dry_run=False)

            if result["success"]:
                status = "✓"
                msg = f"{result['inserted']} results"
                if result['inserted'] == 0:
                    msg = "No new results"
            else:
                status = "✗"
                msg = result["errors"][0] if result["errors"] else "Failed"

            results_log.append(f"{status} {benchmark_id}: {msg}")

        except Exception as e:
            error_msg = str(e)[:50]
            results_log.append(f"✗ {benchmark_id}: {error_msg}")

        completed += 1

        # Update log display
        log_container.code("\n".join(results_log))

    progress_container.progress(1.0, text="Complete!")

    # Update last update timestamp
    try:
        from src.db.connection import set_last_update
        set_last_update(datetime.utcnow())
    except Exception:
        pass

    st.success("Data refresh complete! Reload the page to see updated data.")
    if st.button("🔄 Reload Page"):
        st.rerun()
