"use client";

import { useEffect, useState } from "react";
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

  const currentBenchmark = benchmarks.find((b) => b.id === selectedBenchmark);
  const currentFrontier = selectedBenchmark ? frontier[selectedBenchmark] : [];
  const currentProjections = selectedBenchmark
    ? projections[selectedBenchmark]
    : null;

  // Prepare chart data
  const chartData = prepareChartData(
    currentFrontier || [],
    currentProjections,
    selectedModel
  );

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
      <div className="flex flex-col md:flex-row gap-4 mb-8">
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
                      ? "bg-accent text-base font-medium"
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

      {/* Chart */}
      <div className="card mb-8">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="font-serif text-title text-base-900">
              {currentBenchmark?.name || "Select a benchmark"}
            </h2>
            <p className="text-body-sm text-base-500">
              {CATEGORY_LABELS[currentBenchmark?.category || ""] ||
                currentBenchmark?.category}
            </p>
          </div>

          {currentProjections?.[selectedModel as keyof BenchmarkProjections] && (
            <div className="text-right">
              <div className="text-caption text-base-400">R² Score</div>
              <div className="font-mono text-title-sm text-accent">
                {(
                  currentProjections[selectedModel as keyof BenchmarkProjections]
                    ?.r_squared || 0
                ).toFixed(3)}
              </div>
            </div>
          )}
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
                  domain={[
                    0,
                    currentBenchmark?.scale.max || 100,
                  ]}
                  tickFormatter={(v) =>
                    `${v}${currentBenchmark?.unit === "percent" ? "%" : ""}`
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
                    formatScore(value, currentBenchmark?.unit || "percent"),
                    name,
                  ]}
                  labelFormatter={(d) => formatDate(d)}
                />
                <Legend />

                {/* Confidence interval area */}
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

                {/* Historical data */}
                <Line
                  type="monotone"
                  dataKey="actual"
                  stroke="#c9a227"
                  strokeWidth={2}
                  dot={{ fill: "#c9a227", r: 4 }}
                  name="Historical SOTA"
                  connectNulls
                />

                {/* Projection */}
                <Line
                  type="monotone"
                  dataKey="forecast"
                  stroke="#c9a227"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  name="Forecast"
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
  modelType: string
): Array<{
  date: string;
  actual?: number;
  forecast?: number;
  ci_low?: number;
  ci_high?: number;
}> {
  const data: Record<
    string,
    { date: string; actual?: number; forecast?: number; ci_low?: number; ci_high?: number }
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

  // Add forecast data
  const projection = projections?.[modelType as keyof BenchmarkProjections];
  if (projection?.forecast) {
    projection.forecast.forEach((point) => {
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

  // Sort by date
  return Object.values(data).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );
}
