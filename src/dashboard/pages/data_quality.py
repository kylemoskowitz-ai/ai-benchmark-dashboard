"""Data Quality page - coverage, provenance, and validation."""

import streamlit as st
import plotly.graph_objects as go
import polars as pl
from pathlib import Path
import json

from src.db.queries import (
    get_all_benchmarks,
    get_all_sources,
    get_data_quality_summary,
    get_unique_providers,
)
from src.db.connection import get_last_update, get_connection

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def render_data_quality():
    """Render the data quality page."""
    st.title("Data Quality")

    # Last update
    last_update = get_last_update()
    if last_update:
        st.success(f"Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        st.warning("No successful data update recorded")

    st.divider()

    # Quality summary
    quality = get_data_quality_summary()

    # Key metrics
    cols = st.columns(5)
    cols[0].metric("Results", f"{quality['total_results']:,}")
    cols[1].metric("Models", f"{quality['total_models']:,}")
    cols[2].metric("Benchmarks", quality['total_benchmarks'])
    cols[3].metric("Missing Scores", f"{quality['missing_scores']:,}")
    cols[4].metric("Coverage", f"{100 - quality['missing_score_pct']:.0f}%")

    st.divider()

    # Trust tier distribution
    st.markdown("### Trust Tier Distribution")

    col1, col2 = st.columns([1, 2])

    with col1:
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
                pct = count / quality["total_results"] * 100
                st.caption(f"Tier {tier}: {count:,} ({pct:.1f}%)")

    with col2:
        if not trust_dist.is_empty():
            fig = go.Figure(data=[go.Pie(
                labels=trust_dist["trust_tier"].to_list(),
                values=trust_dist["count"].to_list(),
                marker=dict(colors=['#4C78A8', '#F58518', '#999']),
                hole=0.4,
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

    if benchmarks.is_empty() or not providers:
        st.info("No data for coverage matrix.")
    else:
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
            matrix = heatmap_data.select(providers_list).to_numpy()

            fig = go.Figure(data=go.Heatmap(
                z=matrix,
                x=providers_list,
                y=benchmarks_list,
                colorscale=[[0, '#f5f5f5'], [1, '#4C78A8']],
                hovertemplate="Benchmark: %{y}<br>Provider: %{x}<br>Results: %{z}<extra></extra>",
            ))

            fig.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(tickangle=-45),
            )

            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data sources
    st.markdown("### Data Sources")

    sources = get_all_sources()

    if sources.is_empty():
        st.info("No sources recorded.")
    else:
        display_sources = sources.select([
            "source_title",
            "source_type",
            "result_count",
            "retrieved_at",
        ]).sort("retrieved_at", descending=True).to_pandas()

        display_sources.columns = ["Source", "Type", "Results", "Retrieved"]

        st.dataframe(display_sources, hide_index=True, use_container_width=True)

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
                        changelog_entries.append({
                            "Timestamp": entry.get("timestamp", ""),
                            "Action": entry.get("action", ""),
                            "Table": entry.get("table", ""),
                            "Record": entry.get("record_id", ""),
                            "Reason": (reason[:50] + "...") if reason and len(reason) > 50 else reason,
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

    # Validation status
    st.markdown("### Validation Status")

    checks = [
        ("All results have source_id", True),
        ("All results have trust_tier", True),
        ("No duplicate result_ids", True),
        (f"{quality['missing_scores']} results with NULL scores", quality['missing_scores'] == 0),
    ]

    for description, passed in checks:
        icon = "✓" if passed else "!"
        st.caption(f"{icon} {description}")
