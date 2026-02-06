"use client";

import { useEffect, useMemo, useState } from "react";
import type { Benchmark, FrontierPoint, Result } from "@/lib/types";
import { normalizeScore } from "@/lib/analysis";
import { CATEGORY_LABELS } from "@/lib/types";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ComposedChart,
  Bar,
  BarChart,
} from "recharts";

type QuarterPoint = {
  period: string;
  capability: number | null;
  impact: number | null;
  gap: number | null;
  autonomy_hours: number | null;
  results: number;
  models: number;
  providers: number;
};

type CategorySummary = {
  category: string;
  benchmarks: number;
  activeModels: number;
  leaderScore: number | null;
  leaderModel: string | null;
};

type DiffusionMetric = "results" | "models" | "providers";
type CategoryMetric = "leaderScore" | "activeModels";

const QUARTER_OPTIONS = [
  { label: "Last 8 quarters", value: 8 },
  { label: "Last 12 quarters", value: 12 },
  { label: "Last 20 quarters", value: 20 },
];

export default function ImpactPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [frontier, setFrontier] = useState<Record<string, FrontierPoint[]>>({});
  const [windowSize, setWindowSize] = useState<number>(12);
  const [diffusionMetric, setDiffusionMetric] =
    useState<DiffusionMetric>("models");
  const [categoryMetric, setCategoryMetric] =
    useState<CategoryMetric>("leaderScore");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/results.json").then((r) => r.json()),
      fetch("/data/frontier.json").then((r) => r.json()),
    ])
      .then(([benchData, resultsData, frontierData]) => {
        setBenchmarks(benchData);
        setResults(resultsData);
        setFrontier(frontierData);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const benchmarkById = useMemo(
    () => new Map(benchmarks.map((b) => [b.id, b])),
    [benchmarks]
  );

  const latestMetrics = useMemo(() => {
    const percentBenchmarks = benchmarks.filter((b) => b.unit === "percent");
    const capabilityValues = percentBenchmarks
      .map((benchmark) => {
        const latest = getLatestFrontierScore(frontier[benchmark.id] || []);
        if (latest == null) return null;
        return normalizeScore(latest, benchmark);
      })
      .filter((v): v is number => v != null);

    const capabilityIndex = capabilityValues.length
      ? capabilityValues.reduce((a, b) => a + b, 0) / capabilityValues.length
      : null;

    const impactBenchmark = benchmarks.find((b) => b.id === "remote_labor_index");
    const impactLatest = impactBenchmark
      ? getLatestFrontierScore(frontier[impactBenchmark.id] || [])
      : null;
    const impactIndex =
      impactBenchmark && impactLatest != null
        ? normalizeScore(impactLatest, impactBenchmark)
        : null;

    const metrRows = results.filter(
      (r) => r.benchmark_id === "metr_time_horizons" && (!r.subset || r.subset === "v1.1")
    );
    const metrScore = getBestScore(
      metrRows,
      true
    );
    const autonomyHours = metrScore != null ? metrScore / 60 : null;

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 180);
    const recentRows = results.filter((r) => {
      const d = r.date ? new Date(r.date) : null;
      return d != null && !Number.isNaN(d.getTime()) && d >= cutoff;
    });

    const providerBreadth = new Set(recentRows.map((r) => r.provider)).size;
    const newModelFamilies = new Set(
      recentRows.map((r) => r.model_group || r.model_display || r.model_name)
    ).size;

    return {
      capabilityIndex,
      impactIndex,
      gap:
        capabilityIndex != null && impactIndex != null
          ? capabilityIndex - impactIndex
          : null,
      autonomyHours,
      providerBreadth,
      newModelFamilies,
    };
  }, [benchmarks, frontier, results]);

  const quarterSeries = useMemo<QuarterPoint[]>(() => {
    const rowsWithDate = results
      .map((row) => ({
        ...row,
        parsedDate: row.date ? new Date(row.date) : null,
      }))
      .filter(
        (row) => row.parsedDate && !Number.isNaN(row.parsedDate.getTime())
      ) as (Result & { parsedDate: Date })[];

    if (!rowsWithDate.length) return [];

    const quarterKeys = new Set(
      rowsWithDate.map((row) => toQuarterKey(row.parsedDate))
    );
    const sortedKeys = Array.from(quarterKeys).sort(compareQuarterKeys);

    const byBenchmark = new Map<string, (Result & { parsedDate: Date })[]>();
    rowsWithDate.forEach((row) => {
      if (!byBenchmark.has(row.benchmark_id)) {
        byBenchmark.set(row.benchmark_id, []);
      }
      byBenchmark.get(row.benchmark_id)!.push(row);
    });
    byBenchmark.forEach((list) =>
      list.sort((a, b) => a.parsedDate.getTime() - b.parsedDate.getTime())
    );

    const percentBenchmarks = benchmarks.filter((b) => b.unit === "percent");
    const impactBenchmark = benchmarkById.get("remote_labor_index");

    return sortedKeys.map((quarterKey) => {
      const quarterEnd = getQuarterEnd(quarterKey);

      const capabilityValues: number[] = [];
      for (const benchmark of percentBenchmarks) {
        const rows = (byBenchmark.get(benchmark.id) || []).filter(
          (row) => row.parsedDate <= quarterEnd
        );
        const bestScore = getBestScore(rows, benchmark.higher_is_better);
        if (bestScore == null) continue;
        const normalized = normalizeScore(bestScore, benchmark);
        if (normalized != null) capabilityValues.push(normalized);
      }

      const capability =
        capabilityValues.length > 0
          ? capabilityValues.reduce((a, b) => a + b, 0) / capabilityValues.length
          : null;

      let impact: number | null = null;
      if (impactBenchmark) {
        const impactRows = (byBenchmark.get(impactBenchmark.id) || []).filter(
          (row) => row.parsedDate <= quarterEnd
        );
        const impactScore = getBestScore(
          impactRows,
          impactBenchmark.higher_is_better
        );
        if (impactScore != null) {
          impact = normalizeScore(impactScore, impactBenchmark);
        }
      }

      const metrRows = (byBenchmark.get("metr_time_horizons") || []).filter(
        (row) =>
          row.parsedDate <= quarterEnd && (!row.subset || row.subset === "v1.1")
      );
      const autonomyScore = getBestScore(metrRows, true);
      const autonomyHours = autonomyScore != null ? autonomyScore / 60 : null;

      const inQuarter = rowsWithDate.filter(
        (row) => toQuarterKey(row.parsedDate) === quarterKey
      );
      const uniqueModels = new Set(
        inQuarter.map((r) => r.model_group || r.model_display || r.model_name)
      ).size;
      const uniqueProviders = new Set(inQuarter.map((r) => r.provider)).size;

      return {
        period: quarterKey,
        capability,
        impact,
        gap: capability != null && impact != null ? capability - impact : null,
        autonomy_hours: autonomyHours,
        results: inQuarter.length,
        models: uniqueModels,
        providers: uniqueProviders,
      };
    });
  }, [benchmarks, benchmarkById, results]);

  const visibleQuarterSeries = useMemo(() => {
    return quarterSeries.slice(-windowSize);
  }, [quarterSeries, windowSize]);

  const categorySummary = useMemo<CategorySummary[]>(() => {
    const categories = Array.from(new Set(benchmarks.map((b) => b.category)));
    return categories
      .map((category) => {
        const categoryBenchmarks = benchmarks.filter((b) => b.category === category);
        if (!categoryBenchmarks.length) {
          return null;
        }

        let leaderScore: number | null = null;
        let leaderModel: string | null = null;
        for (const benchmark of categoryBenchmarks) {
          if (!benchmark.sota) continue;
          const normalized = normalizeScore(benchmark.sota.score, benchmark);
          if (normalized == null) continue;
          if (leaderScore == null || normalized > leaderScore) {
            leaderScore = normalized;
            leaderModel = benchmark.sota.model_display || benchmark.sota.model_name;
          }
        }

        const benchmarkIds = new Set(categoryBenchmarks.map((b) => b.id));
        const activeModels = new Set(
          results
            .filter((r) => benchmarkIds.has(r.benchmark_id))
            .map((r) => r.model_group || r.model_display || r.model_name)
        ).size;

        return {
          category,
          benchmarks: categoryBenchmarks.length,
          activeModels,
          leaderScore,
          leaderModel,
        };
      })
      .filter((entry): entry is CategorySummary => entry != null)
      .sort((a, b) => (b.leaderScore ?? -Infinity) - (a.leaderScore ?? -Infinity));
  }, [benchmarks, results]);

  const categoryChartData = useMemo(
    () =>
      categorySummary.map((entry) => ({
        category: CATEGORY_LABELS[entry.category] || entry.category,
        leaderScore: entry.leaderScore ?? 0,
        activeModels: entry.activeModels,
      })),
    [categorySummary]
  );

  const headline = useMemo(() => {
    const latest = visibleQuarterSeries[visibleQuarterSeries.length - 1];
    const prev = visibleQuarterSeries[visibleQuarterSeries.length - 2];
    if (!latest) return "Not enough quarterly history yet.";

    const parts: string[] = [];
    if (latest.capability != null && latest.impact != null) {
      const gap = latest.capability - latest.impact;
      const gapLabel = gap >= 0 ? "capability is ahead of impact" : "impact is ahead of capability";
      parts.push(`${gapLabel} by ${Math.abs(gap).toFixed(1)} points`);
    }
    if (latest.autonomy_hours != null) {
      parts.push(`METR autonomy is ${latest.autonomy_hours.toFixed(1)} hours`);
    }
    if (prev && latest[diffusionMetric] != null && prev[diffusionMetric] != null) {
      const delta = latest[diffusionMetric] - prev[diffusionMetric];
      const direction = delta >= 0 ? "increased" : "decreased";
      parts.push(`${diffusionMetricLabel(diffusionMetric)} ${direction} by ${Math.abs(delta).toFixed(1)} QoQ`);
    }
    return parts.length ? parts.join(" · ") : "Not enough quarterly history yet.";
  }, [visibleQuarterSeries, diffusionMetric]);

  if (loading) {
    return (
      <div className="container-wide py-12">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-base-50 rounded w-1/3" />
          <div className="h-96 bg-base-50 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="container-wide py-12 space-y-8">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h1 className="font-serif text-display-sm text-base-900">
            Impact & Diffusion
          </h1>
          <p className="mt-2 text-body text-base-500 max-w-3xl">
            Capability growth and real-world diffusion tracked together. Values
            are benchmark-driven proxies, shown over quarterly time slices.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            value={windowSize}
            onChange={(e) => setWindowSize(Number(e.target.value))}
            className="px-3 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900 text-body-sm"
          >
            {QUARTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            value={diffusionMetric}
            onChange={(e) => setDiffusionMetric(e.target.value as DiffusionMetric)}
            className="px-3 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900 text-body-sm"
          >
            <option value="models">Diffusion: model families</option>
            <option value="providers">Diffusion: providers</option>
            <option value="results">Diffusion: result volume</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          title="Capability Index"
          value={
            latestMetrics.capabilityIndex != null
              ? latestMetrics.capabilityIndex.toFixed(1)
              : "—"
          }
          subtitle="Average normalized frontier score"
        />
        <MetricCard
          title="Impact Index"
          value={
            latestMetrics.impactIndex != null
              ? latestMetrics.impactIndex.toFixed(1)
              : "—"
          }
          subtitle="Remote labor adoption proxy"
        />
        <MetricCard
          title="Capability-Impact Gap"
          value={latestMetrics.gap != null ? latestMetrics.gap.toFixed(1) : "—"}
          subtitle="Positive means impact lags capability"
        />
        <MetricCard
          title="Autonomy Horizon"
          value={
            latestMetrics.autonomyHours != null
              ? `${latestMetrics.autonomyHours.toFixed(1)} hrs`
              : "—"
          }
          subtitle="METR P50 (v1.1 preferred)"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricCard
          title="Provider Breadth (180d)"
          value={latestMetrics.providerBreadth.toLocaleString("en-US")}
          subtitle="Distinct providers shipping benchmarked models"
        />
        <MetricCard
          title="Active Model Families (180d)"
          value={latestMetrics.newModelFamilies.toLocaleString("en-US")}
          subtitle="Distinct model groups with recent benchmark activity"
        />
      </div>

      <div className="card card-muted">
        <div className="text-caption uppercase tracking-wider text-base-500">
          What This Means
        </div>
        <div className="mt-2 text-body text-base-900">{headline}</div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-title text-base-900">
            Capability vs Impact Trajectory
          </h2>
          <span className="text-caption text-base-400">
            Quarterly frontier index (0-100)
          </span>
        </div>
        <div className="h-[320px]">
          {visibleQuarterSeries.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={visibleQuarterSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="period" stroke="#71717a" />
                <YAxis stroke="#71717a" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#a1a1aa" }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="capability"
                  stroke="var(--color-accent)"
                  strokeWidth={2}
                  dot={false}
                  name="Capability index"
                />
                <Line
                  type="monotone"
                  dataKey="impact"
                  stroke="#60a5fa"
                  strokeWidth={2}
                  dot={false}
                  name="Impact index"
                />
                <Line
                  type="monotone"
                  dataKey="gap"
                  stroke="#f97316"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={false}
                  name="Gap"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-base-500">
              Not enough data to compute quarterly trajectories.
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-title text-base-900">
            Diffusion & Autonomy
          </h2>
          <span className="text-caption text-base-400">
            Selected diffusion metric with METR horizon overlay
          </span>
        </div>
        <div className="h-[320px]">
          {visibleQuarterSeries.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={visibleQuarterSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="period" stroke="#71717a" />
                <YAxis yAxisId="left" stroke="#71717a" />
                <YAxis yAxisId="right" orientation="right" stroke="#71717a" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#a1a1aa" }}
                />
                <Legend />
                <Bar
                  yAxisId="left"
                  dataKey={diffusionMetric}
                  fill="color-mix(in srgb, var(--color-accent) 70%, transparent)"
                  name={diffusionMetricLabel(diffusionMetric)}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="autonomy_hours"
                  stroke="#34d399"
                  strokeWidth={2}
                  dot={false}
                  name="METR autonomy hours"
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-base-500">
              Not enough data to compute diffusion metrics.
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-title text-base-900">
            Task-Dimension Readiness
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-caption text-base-400">
              Category leadership and active model depth
            </span>
            <select
              value={categoryMetric}
              onChange={(e) =>
                setCategoryMetric(e.target.value as CategoryMetric)
              }
              className="px-2 py-1 bg-base-50 border border-base-200 rounded text-caption text-base-500"
            >
              <option value="leaderScore">View: leader score</option>
              <option value="activeModels">View: active models</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {categorySummary.map((entry) => (
            <div
              key={entry.category}
              className="rounded-lg border border-base-200 bg-base-50 px-4 py-4"
            >
              <div className="text-caption uppercase tracking-wider text-base-500">
                {CATEGORY_LABELS[entry.category] || entry.category}
              </div>
              <div className="mt-2 font-mono text-title-sm text-accent">
                {entry.leaderScore != null ? entry.leaderScore.toFixed(1) : "—"}
              </div>
              <div className="text-body-sm text-base-500 mt-1">
                {entry.leaderModel || "No leader yet"}
              </div>
              <div className="mt-3 text-caption text-base-400">
                {entry.benchmarks} benchmarks, {entry.activeModels} active model groups
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 h-[260px]">
          {categoryChartData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="category" stroke="#71717a" />
                <YAxis stroke="#71717a" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#a1a1aa" }}
                />
                <Legend />
                <Bar
                  dataKey={categoryMetric}
                  fill={
                    categoryMetric === "leaderScore"
                      ? "color-mix(in srgb, var(--color-accent) 80%, transparent)"
                      : "#60a5fa"
                  }
                  name={
                    categoryMetric === "leaderScore"
                      ? "Leader score (0-100)"
                      : "Active model groups"
                  }
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-base-500">
              Not enough category data.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string;
  subtitle: string;
}) {
  return (
    <div className="card shadow-soft">
      <div className="text-caption uppercase tracking-wider text-base-500">
        {title}
      </div>
      <div className="mt-3 font-mono text-title-sm text-accent">{value}</div>
      <div className="text-body-sm text-base-500 mt-1">{subtitle}</div>
    </div>
  );
}

function getLatestFrontierScore(points: FrontierPoint[]): number | null {
  if (!points.length) return null;
  const sorted = [...points].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );
  const latest = sorted[sorted.length - 1];
  return latest?.score ?? null;
}

function getBestScore(rows: Result[], higherIsBetter: boolean): number | null {
  if (!rows.length) return null;
  const scores = rows
    .map((r) => r.score)
    .filter((score): score is number => score != null);
  if (!scores.length) return null;
  return higherIsBetter ? Math.max(...scores) : Math.min(...scores);
}

function toQuarterKey(d: Date): string {
  const quarter = Math.floor(d.getMonth() / 3) + 1;
  return `${d.getFullYear()} Q${quarter}`;
}

function compareQuarterKeys(a: string, b: string) {
  const [aYear, aQuarter] = parseQuarter(a);
  const [bYear, bQuarter] = parseQuarter(b);
  if (aYear !== bYear) return aYear - bYear;
  return aQuarter - bQuarter;
}

function parseQuarter(value: string): [number, number] {
  const match = /^(\d{4}) Q([1-4])$/.exec(value);
  if (!match) return [0, 0];
  return [Number(match[1]), Number(match[2])];
}

function getQuarterEnd(quarterKey: string): Date {
  const [year, quarter] = parseQuarter(quarterKey);
  const month = quarter * 3;
  return new Date(year, month, 0, 23, 59, 59, 999);
}

function diffusionMetricLabel(metric: DiffusionMetric): string {
  if (metric === "results") return "Result volume";
  if (metric === "providers") return "Active providers";
  return "Active model families";
}
