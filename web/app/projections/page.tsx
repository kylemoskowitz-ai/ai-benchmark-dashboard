"use client";

import { useEffect, useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";
import type { Benchmark, FrontierPoint, BenchmarkProjections } from "@/lib/types";
import { formatScore, formatDate } from "@/lib/data";
import { CATEGORY_LABELS } from "@/lib/types";
import { estimateMaeFromR2 } from "@/lib/analysis";

export default function ProjectionsPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [frontier, setFrontier] = useState<Record<string, FrontierPoint[]>>({});
  const [projections, setProjections] = useState<
    Record<string, BenchmarkProjections>
  >({});
  const [selectedBenchmark, setSelectedBenchmark] = useState<string | null>(
    null
  );
  const [selectedModel, setSelectedModel] = useState<string>("logistic");
  const [pace, setPace] = useState<number>(1);
  const [viewMode, setViewMode] = useState<"score" | "speed">("score");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/frontier.json").then((r) => r.json()),
      fetch("/data/projections.json").then((r) => r.json()),
    ])
      .then(([benchData, frontierData, projData]) => {
        setBenchmarks(benchData);
        setFrontier(frontierData);
        setProjections(projData);
        // Select first benchmark with projections
        const firstWithProjections = benchData.find(
          (b: Benchmark) => projData[b.id]
        );
        setSelectedBenchmark(firstWithProjections?.id || null);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load data:", err);
        setLoading(false);
      });
  }, []);

  const currentBenchmark = benchmarks.find((b) => b.id === selectedBenchmark);
  const currentFrontier = selectedBenchmark ? frontier[selectedBenchmark] : [];
  const currentProjections = selectedBenchmark
    ? projections[selectedBenchmark]
    : null;
  const selectedForecast =
    currentProjections?.[selectedModel as keyof BenchmarkProjections]?.forecast ||
    [];
  const adjustedForecast = applyPace(selectedForecast, pace);

  // Prepare chart data
  const chartData = prepareChartData(
    currentFrontier || [],
    currentProjections,
    selectedModel,
    pace,
    viewMode
  );

  const pointsUsed = currentFrontier?.length ?? 0;
  const fitR2 =
    currentProjections?.[selectedModel as keyof BenchmarkProjections]?.r_squared;
  const maeEstimate = useMemo(
    () => estimateMaeFromR2(currentFrontier || [], fitR2),
    [currentFrontier, fitR2]
  );

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

  const modelLabels: Record<string, string> = {
    linear: "Linear",
    logistic: "Logistic (Saturation)",
    power_law: "Power Law",
  };

  return (
    <div className="container-wide py-12">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-display-sm text-base-900">
          Progress Projections
        </h1>
        <p className="mt-2 text-body text-base-500">
          Forecasting future capability gains using historical SOTA trends
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-6 mb-8">
        <div className="flex flex-col md:flex-row gap-4">
        {/* Benchmark selector */}
        <div className="flex-1">
          <label className="block text-body-sm text-base-500 mb-2">
            Benchmark
          </label>
          <select
            value={selectedBenchmark || ""}
            onChange={(e) => setSelectedBenchmark(e.target.value)}
            className="w-full px-4 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900 focus:outline-none focus:border-accent"
          >
            {benchmarks
              .filter((b) => projections[b.id])
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
          </select>
        </div>

        {/* Model selector */}
        <div className="w-full md:w-64">
          <label className="block text-body-sm text-base-500 mb-2">
            Projection Model
          </label>
          <div className="flex gap-2">
            {(["logistic", "linear", "power_law"] as const).map((model) => {
              const projection = currentProjections?.[model];
              return (
                <button
                  key={model}
                  onClick={() => setSelectedModel(model)}
                  disabled={!projection}
                  className={`flex-1 px-3 py-2 rounded-lg text-body-sm transition-colors ${
                    selectedModel === model
                      ? "bg-accent text-base-900 font-medium"
                      : projection
                      ? "bg-base-50 text-base-500 hover:bg-base-100"
                      : "bg-base-50 text-base-300 cursor-not-allowed"
                  }`}
                >
                  {modelLabels[model]}
                </button>
              );
            })}
          </div>
        </div>
        </div>

        {/* Scenario controls */}
        <div className="card card-muted">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="text-caption uppercase tracking-wider text-base-500">
                Scenario Pace
              </div>
              <div className="text-body-sm text-base-500 mt-1">
                Adjust projected improvement speed
              </div>
            </div>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0.8"
                max="1.2"
                step="0.05"
                value={pace}
                onChange={(e) => setPace(Number(e.target.value))}
                className="w-48"
              />
              <span className="font-mono text-body-sm text-base-900">
                {pace.toFixed(2)}x
              </span>
            </div>
            <div className="flex items-center gap-2">
              {(["score", "speed"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`px-3 py-2 rounded-lg text-body-sm transition-colors ${
                    viewMode === mode
                      ? "bg-accent text-base-900 font-medium"
                      : "bg-base-50 text-base-500 hover:bg-base-100"
                  }`}
                >
                  {mode === "score" ? "Score View" : "Speed View"}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="card mb-8">
        <div className="mb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="font-serif text-title text-base-900">
              {currentBenchmark?.name || "Select a benchmark"}
            </h2>
            <p className="text-body-sm text-base-500">
              {CATEGORY_LABELS[currentBenchmark?.category || ""] ||
                currentBenchmark?.category}
            </p>
          </div>

          <div className="flex gap-6">
            <div>
              <div className="text-caption text-base-400">R² Score</div>
              <div className="font-mono text-title-sm text-accent">
                {fitR2 != null ? fitR2.toFixed(3) : "—"}
              </div>
            </div>
            <div>
              <div className="text-caption text-base-400">Est. MAE</div>
              <div className="font-mono text-title-sm text-base-900">
                {maeEstimate != null
                  ? maeEstimate.toFixed(2)
                  : "—"}
              </div>
            </div>
            <div>
              <div className="text-caption text-base-400">Points used</div>
              <div className="font-mono text-title-sm text-base-900">
                {pointsUsed}
              </div>
            </div>
          </div>
          <div className="text-caption text-base-400">
            MAE estimated from R² and variance (approximate).
          </div>
        </div>

        <div className="h-96">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="date"
                  stroke="#71717a"
                  tickFormatter={(d) =>
                    new Date(d).toLocaleDateString("en-US", {
                      month: "short",
                      year: "2-digit",
                    })
                  }
                />
                <YAxis
                  stroke="#71717a"
                  domain={
                    viewMode === "speed"
                      ? ["auto", "auto"]
                      : [0, currentBenchmark?.scale.max || 100]
                  }
                  tickFormatter={(v) =>
                    viewMode === "speed"
                      ? `${v.toFixed(1)}`
                      : `${v}${currentBenchmark?.unit === "percent" ? "%" : ""}`
                  }
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#a1a1aa" }}
                  formatter={(value: number, name: string) => [
                    viewMode === "speed"
                      ? `${value.toFixed(2)} / mo`
                      : formatScore(value, currentBenchmark?.unit || "percent"),
                    name,
                  ]}
                  labelFormatter={(d) => formatDate(d)}
                />
                <Legend />

                {/* Confidence interval area */}
                {viewMode === "score" && (
                  <>
                    <Area
                      type="monotone"
                      dataKey="ci_high"
                      stroke="transparent"
                      fill="#c9a227"
                      fillOpacity={0.1}
                      name="CI High"
                      legendType="none"
                    />
                    <Area
                      type="monotone"
                      dataKey="ci_low"
                      stroke="transparent"
                      fill="#0a0a0b"
                      fillOpacity={1}
                      name="CI Low"
                      legendType="none"
                    />
                  </>
                )}

                {/* Historical data */}
                <Line
                  type="monotone"
                  dataKey={viewMode === "speed" ? "actual_speed" : "actual"}
                  stroke="#c9a227"
                  strokeWidth={2}
                  dot={{ fill: "#c9a227", r: 4 }}
                  name={viewMode === "speed" ? "Historical Speed" : "Historical SOTA"}
                  connectNulls
                />

                {/* Projection */}
                <Line
                  type="monotone"
                  dataKey={viewMode === "speed" ? "forecast_speed" : "forecast"}
                  stroke="#c9a227"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  name={viewMode === "speed" ? "Forecast Speed" : "Forecast"}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-base-500">
              No projection data available for this benchmark
            </div>
          )}
        </div>
      </div>

      {/* Forecast milestones & benchmark list */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="card">
          <h3 className="font-serif text-title-sm text-base-900 mb-4">
            Forecast Milestones
          </h3>
          {currentBenchmark?.unit === "percent" && currentProjections ? (
            <MilestoneTable
              forecast={adjustedForecast}
            />
          ) : (
            <div className="text-body-sm text-base-500">
              Milestones available for percentage benchmarks only.
            </div>
          )}
        </div>
        <div className="card lg:col-span-2">
          <h3 className="font-serif text-title-sm text-base-900 mb-4">
            Benchmarks Closest to Saturation
          </h3>
          <BenchmarkForecastList
            benchmarks={benchmarks}
            projections={projections}
          />
        </div>
      </div>

      {/* Model explanation */}
      <div className="card">
        <h3 className="font-serif text-title-sm text-base-900 mb-4">
          About the Projection Models
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <ModelExplanation
            title="Linear"
            description="Extrapolates the recent trend assuming constant rate of improvement. Best for benchmarks with steady progress."
            active={selectedModel === "linear"}
          />
          <ModelExplanation
            title="Logistic (Saturation)"
            description="Assumes performance will saturate as it approaches the maximum score. More realistic for percentage-based benchmarks."
            active={selectedModel === "logistic"}
          />
          <ModelExplanation
            title="Power Law"
            description="Models improvement as a power law function of time. Captures accelerating or decelerating trends."
            active={selectedModel === "power_law"}
          />
        </div>
      </div>
    </div>
  );
}

function ModelExplanation({
  title,
  description,
  active,
}: {
  title: string;
  description: string;
  active: boolean;
}) {
  return (
    <div
      className={`p-4 rounded-lg border transition-colors ${
        active
          ? "border-accent bg-accent/5"
          : "border-base-200 bg-base-50/50"
      }`}
    >
      <h4
        className={`font-medium mb-2 ${
          active ? "text-accent" : "text-base-700"
        }`}
      >
        {title}
      </h4>
      <p className="text-body-sm text-base-500">{description}</p>
    </div>
  );
}

function prepareChartData(
  frontier: FrontierPoint[],
  projections: BenchmarkProjections | null,
  modelType: string,
  pace: number,
  viewMode: "score" | "speed"
): Array<{
  date: string;
  actual?: number;
  forecast?: number;
  ci_low?: number;
  ci_high?: number;
  actual_speed?: number;
  forecast_speed?: number;
}> {
  const data: Record<
    string,
    {
      date: string;
      actual?: number;
      forecast?: number;
      ci_low?: number;
      ci_high?: number;
      actual_speed?: number;
      forecast_speed?: number;
    }
  > = {};

  // Add historical data
  frontier.forEach((point) => {
    if (point.date) {
      data[point.date] = {
        date: point.date,
        actual: point.score,
      };
    }
  });

  // Add forecast data (pace-adjusted)
  const projection = projections?.[modelType as keyof BenchmarkProjections];
  if (projection?.forecast) {
    const adjusted = applyPace(projection.forecast, pace);
    adjusted.forEach((point) => {
      if (point.date) {
        if (data[point.date]) {
          data[point.date].forecast = point.value;
          data[point.date].ci_low = point.ci_low;
          data[point.date].ci_high = point.ci_high;
        } else {
          data[point.date] = {
            date: point.date,
            forecast: point.value,
            ci_low: point.ci_low,
            ci_high: point.ci_high,
          };
        }
      }
    });
  }

  // Add speed metrics (per month)
  const ordered = Object.values(data).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );
  for (let i = 1; i < ordered.length; i += 1) {
    const prev = ordered[i - 1];
    const curr = ordered[i];
    const months =
      (new Date(curr.date).getTime() - new Date(prev.date).getTime()) /
      (1000 * 60 * 60 * 24 * 30.44);
    if (months > 0) {
      if (prev.actual != null && curr.actual != null) {
        curr.actual_speed = (curr.actual - prev.actual) / months;
      }
      if (prev.forecast != null && curr.forecast != null) {
        curr.forecast_speed = (curr.forecast - prev.forecast) / months;
      }
    }
  }

  // Sort by date
  return ordered;
}

function applyPace(
  forecast: { date: string; value: number; ci_low: number; ci_high: number }[],
  pace: number
) {
  if (forecast.length === 0 || pace === 1) return forecast;
  const base = forecast[0].value;
  return forecast.map((point) => {
    const delta = point.value - base;
    return {
      ...point,
      value: base + delta * pace,
      ci_low: base + (point.ci_low - base) * pace,
      ci_high: base + (point.ci_high - base) * pace,
    };
  });
}

function MilestoneTable({
  forecast,
}: {
  forecast: { date: string; value: number }[];
}) {
  const milestones = [70, 85, 95];
  return (
    <div className="space-y-2">
      {milestones.map((target) => {
        const hit = forecast.find((p) => p.value >= target);
        return (
          <div key={target} className="flex items-center justify-between text-body-sm text-base-500">
            <span>{target}%</span>
            <span className="font-mono text-base-900">
              {hit ? formatDate(hit.date) : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function BenchmarkForecastList({
  benchmarks,
  projections,
}: {
  benchmarks: Benchmark[];
  projections: Record<string, BenchmarkProjections>;
}) {
  const items = benchmarks
    .filter((b) => b.unit === "percent")
    .map((b) => {
      const proj =
        projections[b.id]?.logistic ||
        projections[b.id]?.power_law ||
        projections[b.id]?.linear;
      if (!proj?.forecast?.length) return null;
      const target = b.scale?.max ?? 100;
      const hit = proj.forecast.find((p) => p.value >= target * 0.9);
      return hit
        ? { benchmark: b, date: hit.date }
        : null;
    })
    .filter(Boolean) as { benchmark: Benchmark; date: string }[];

  const sorted = items.sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  return (
    <div className="space-y-3">
      {sorted.slice(0, 6).map((item) => (
        <div key={item.benchmark.id} className="flex items-center justify-between">
          <span className="text-body-sm text-base-500">
            {item.benchmark.name}
          </span>
          <span className="font-mono text-body-sm text-base-900">
            {formatDate(item.date)}
          </span>
        </div>
      ))}
      {sorted.length === 0 && (
        <div className="text-body-sm text-base-500">No forecast milestones yet.</div>
      )}
    </div>
  );
}
