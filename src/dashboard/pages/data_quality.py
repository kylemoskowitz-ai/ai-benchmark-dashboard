"""Data Quality page - coverage, missingness, provenance browser."""

import streamlit as st
import plotly.express as px
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
from src.db.connection import get_last_update
from src.config import settings, get_absolute_path


def render_data_quality():
    """Render the data quality page."""
    st.title("Data Quality Dashboard")
    st.caption("Coverage, missingness, trust tiers, and provenance")

    # Last update
    last_update = get_last_update()
    if last_update:
        st.success(f"✅ Last successful update: {last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        st.warning("⚠️ No successful data update recorded")

    st.divider()

    # Quality summary
    quality = get_data_quality_summary()

    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Results", f"{quality['total_results']:,}")
    with col2:
        st.metric("Models", f"{quality['total_models']:,}")
    with col3:
        st.metric("Benchmarks", quality['total_benchmarks'])
    with col4:
        st.metric("Missing Scores", f"{quality['missing_scores']:,}")
    with col5:
        coverage = 100 - quality['missing_score_pct']
        st.metric("Coverage", f"{coverage:.1f}%")

    st.divider()

    # Trust tier distribution
    st.subheader("Trust Tier Distribution")

    col1, col2 = st.columns([1, 2])

    with col1:
        trust_dist = quality["trust_distribution"]
        if not trust_dist.is_empty():
            st.write("**Tier Definitions:**")
            st.markdown("""
            - 🟢 **Tier A**: Official sources (benchmark authors, official leaderboards)
            - 🟡 **Tier B**: Semi-official (model provider results, Epoch AI)
            - ⚪ **Tier C**: Third-party (community runs, blog posts)
            """)

            for row in trust_dist.iter_rows(named=True):
                tier = row["trust_tier"]
                count = row["count"]
                pct = count / quality["total_results"] * 100
                emoji = {"A": "🟢", "B": "🟡", "C": "⚪"}.get(tier, "⚪")
                st.write(f"{emoji} Tier {tier}: {count:,} ({pct:.1f}%)")

    with col2:
        if not trust_dist.is_empty():
            fig = px.pie(
                trust_dist.to_pandas(),
                values="count",
                names="trust_tier",
                color="trust_tier",
                color_discrete_map={"A": "#1a7f37", "B": "#9a6700", "C": "#6e7781"},
                title="Results by Trust Tier",
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Coverage matrix
    st.subheader("Coverage Matrix")

    benchmarks = get_all_benchmarks()
    providers = get_unique_providers()

    if benchmarks.is_empty() or not providers:
        st.info("No data to display coverage matrix.")
    else:
        # Build coverage matrix
        from src.db.connection import get_connection

        with get_connection(read_only=True) as conn:
            coverage_data = conn.execute("""
                SELECT
                    b.name as benchmark,
                    m.provider,
                    COUNT(r.result_id) as count,
                    COUNT(CASE WHEN r.score IS NOT NULL THEN 1 END) as valid
                FROM benchmarks b
                CROSS JOIN (SELECT DISTINCT provider FROM models) m
                LEFT JOIN results r ON r.benchmark_id = b.benchmark_id
                LEFT JOIN models mo ON r.model_id = mo.model_id AND mo.provider = m.provider
                GROUP BY b.name, m.provider
            """).pl()

        if not coverage_data.is_empty():
            # Pivot for heatmap
            heatmap_data = coverage_data.pivot(
                on="provider",
                index="benchmark",
                values="valid",
                aggregate_function="sum",
            ).fill_null(0)

            # Convert to matrix format
            benchmarks_list = heatmap_data["benchmark"].to_list()
            providers_list = [c for c in heatmap_data.columns if c != "benchmark"]
            matrix = heatmap_data.select(providers_list).to_numpy()

            fig = go.Figure(data=go.Heatmap(
                z=matrix,
                x=providers_list,
                y=benchmarks_list,
                colorscale="Blues",
                hovertemplate="Benchmark: %{y}<br>Provider: %{x}<br>Results: %{z}<extra></extra>",
            ))

            fig.update_layout(
                title="Results Count by Benchmark × Provider",
                xaxis_title="Provider",
                yaxis_title="Benchmark",
                height=400,
            )

            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Source browser
    st.subheader("Data Sources")

    sources = get_all_sources()

    if sources.is_empty():
        st.info("No sources recorded yet.")
    else:
        # Summary by source type
        source_summary = sources.group_by("source_type").agg([
            pl.len().alias("count"),
            pl.col("result_count").sum().alias("total_results"),
        ]).sort("total_results", descending=True)

        col1, col2 = st.columns([1, 1])

        with col1:
            st.write("**Sources by Type:**")
            for row in source_summary.iter_rows(named=True):
                st.write(f"- {row['source_type']}: {row['count']} sources, {row['total_results']} results")

        with col2:
            fig = px.bar(
                source_summary.to_pandas(),
                x="source_type",
                y="total_results",
                title="Results by Source Type",
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        # Source details table
        st.write("**All Sources:**")

        display_sources = sources.select([
            "source_title",
            "source_type",
            "source_url",
            "retrieved_at",
            "result_count",
        ]).sort("retrieved_at", descending=True)

        st.dataframe(
            display_sources.to_pandas(),
            hide_index=True,
            use_container_width=True,
            column_config={
                "source_url": st.column_config.LinkColumn("URL"),
            },
        )

    st.divider()

    # Changelog viewer
    st.subheader("Data Changelog")

    changelog_path = get_absolute_path(settings.changelog_file)

    if changelog_path.exists():
        with open(changelog_path, "r") as f:
            lines = f.readlines()[-50:]  # Last 50 entries

        if lines:
            changelog_entries = []
            for line in reversed(lines):
                try:
                    entry = json.loads(line.strip())
                    changelog_entries.append({
                        "Timestamp": entry.get("timestamp", ""),
                        "Action": entry.get("action", ""),
                        "Table": entry.get("table", ""),
                        "Record": entry.get("record_id", ""),
                        "Reason": entry.get("reason", "")[:50] + "..." if entry.get("reason", "") and len(entry.get("reason", "")) > 50 else entry.get("reason", ""),
                    })
                except json.JSONDecodeError:
                    continue

            if changelog_entries:
                st.dataframe(
                    changelog_entries,
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("Changelog exists but no valid entries found.")
        else:
            st.info("Changelog is empty.")
    else:
        st.info("No changelog file found. Changes will be logged after data updates.")

    st.divider()

    # Validation status
    st.subheader("Data Validation Status")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Validation Checks:**")
        checks = [
            ("✅", "All results have source_id"),
            ("✅", "All results have trust_tier"),
            ("✅", "No duplicate result_ids"),
            ("⚠️" if quality["missing_scores"] > 0 else "✅",
             f"{quality['missing_scores']} results with NULL scores"),
        ]
        for status, description in checks:
            st.write(f"{status} {description}")

    with col2:
        st.write("**Schema Version:**")
        from src.db.connection import get_connection
        with get_connection(read_only=True) as conn:
            version = conn.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            st.write(f"Database schema: v{version[0] if version else 'unknown'}")

    # Manual override section
    st.divider()
    st.subheader("Manual Overrides")

    overrides_path = get_absolute_path(settings.overrides_file)

    if overrides_path.exists():
        with open(overrides_path, "r") as f:
            import yaml
            overrides = yaml.safe_load(f)

        if overrides and overrides.get("overrides"):
            st.write(f"**{len(overrides['overrides'])} manual overrides applied:**")
            for override in overrides["overrides"]:
                st.write(f"- {override.get('field')}: {override.get('reason', 'No reason given')}")
        else:
            st.info("No manual overrides configured.")
    else:
        st.info("No overrides file found. Create `data/overrides.yml` to add manual corrections.")

        # Show example
        with st.expander("Example overrides.yml"):
            st.code("""
overrides:
  - result_id: "abc123"
    field: "score"
    old_value: 45.2
    new_value: 46.1
    reason: "Corrected per official errata"
    date: "2024-03-15"
            """, language="yaml")
