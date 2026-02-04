"use client";

import { useEffect, useMemo, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { Benchmark, Result } from "@/lib/types";
import { formatScore, formatDate, parseDate } from "@/lib/data";
import { normalizeScore } from "@/lib/analysis";
import { PROVIDER_COLORS, CATEGORY_LABELS } from "@/lib/types";
import { TrustBadge } from "@/components/TrustBadge";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

type Filters = {
  providers: string[];
  trust: string[];
  category: string;
  search: string;
  startDate: string;
  endDate: string;
  onlyOfficial: boolean;
  normalize: boolean;
  metrVersion: string;
};

function ExplorerContent() {
  const searchParams = useSearchParams();
  const selectedBenchmark = searchParams.get("benchmark");

  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [activeBenchmark, setActiveBenchmark] = useState<string | null>(null);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [selectedResult, setSelectedResult] = useState<Result | null>(null);
  const [modelQuery, setModelQuery] = useState("");
  const [filters, setFilters] = useState<Filters>({
    providers: [],
    trust: [],
    category: "all",
    search: "",
    startDate: "",
    endDate: "",
    onlyOfficial: false,
    normalize: false,
    metrVersion: "all",
  });
  const [loading, setLoading] = useState(true);

  const getModelLabel = (result: Result) =>
    getResultModelLabel(result);
  const getModelKey = (result: Result) =>
    getResultModelKey(result);

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/results.json").then((r) => r.json()),
    ])
      .then(([benchData, resultsData]) => {
        setBenchmarks(benchData);
        setResults(resultsData);
        setActiveBenchmark(selectedBenchmark || (benchData[0]?.id ?? null));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedBenchmark]);

  const currentBenchmark = benchmarks.find((b) => b.id === activeBenchmark);

  const providers = useMemo(() => {
    const set = new Set(results.map((r) => r.provider));
    return Array.from(set).sort();
  }, [results]);

  const categories = useMemo(() => {
    const set = new Set(benchmarks.map((b) => b.category));
    return ["all", ...Array.from(set)];
  }, [benchmarks]);

  const visibleBenchmarks = useMemo(() => {
    if (filters.category === "all") return benchmarks;
    return benchmarks.filter((b) => b.category === filters.category);
  }, [benchmarks, filters.category]);

  useEffect(() => {
    if (!activeBenchmark) return;
    if (!visibleBenchmarks.find((b) => b.id === activeBenchmark)) {
      setActiveBenchmark(visibleBenchmarks[0]?.id ?? null);
    }
  }, [visibleBenchmarks, activeBenchmark]);

  const benchmarkResults = useMemo(() => {
    if (!activeBenchmark) return [];
    let filtered = results.filter((r) => r.benchmark_id === activeBenchmark);

    if (filters.providers.length) {
      filtered = filtered.filter((r) => filters.providers.includes(r.provider));
    }

    if (filters.trust.length) {
      filtered = filtered.filter((r) => filters.trust.includes(r.trust_tier));
    }

    if (filters.onlyOfficial) {
      filtered = filtered.filter((r) => r.trust_tier === "A");
    }

    if (
      currentBenchmark?.id === "metr_time_horizons" &&
      filters.metrVersion !== "all"
    ) {
      filtered = filtered.filter((r) => r.subset === filters.metrVersion);
    }

    if (filters.search) {
      const q = filters.search.toLowerCase();
      filtered = filtered.filter((r) => {
        const label = getModelLabel(r).toLowerCase();
        return label.includes(q) || r.model_name.toLowerCase().includes(q);
      });
    }

    if (filters.startDate) {
      const start = parseDate(filters.startDate);
      filtered = filtered.filter((r) => {
        const d = parseDate(r.date);
        return d && start ? d >= start : true;
      });
    }

    if (filters.endDate) {
      const end = parseDate(filters.endDate);
      filtered = filtered.filter((r) => {
        const d = parseDate(r.date);
        return d && end ? d <= end : true;
      });
    }

    const higherIsBetter = currentBenchmark?.higher_is_better ?? true;
    filtered = filtered.sort((a, b) =>
      higherIsBetter ? b.score - a.score : a.score - b.score
    );
    return filtered;
  }, [activeBenchmark, results, filters, currentBenchmark]);

  const modelOptions = useMemo(() => {
    const map = new Map<string, string>();
    results
      .filter((r) => r.benchmark_id === activeBenchmark)
      .forEach((r) => {
        const key = getModelKey(r);
        if (!map.has(key)) {
          map.set(key, getModelLabel(r));
        }
      });
    return Array.from(map.entries())
      .map(([key, label]) => ({ key, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [results, activeBenchmark]);

  const filteredModelOptions = useMemo(() => {
    if (!modelQuery) return modelOptions;
    const q = modelQuery.toLowerCase();
    return modelOptions.filter((m) => m.label.toLowerCase().includes(q));
  }, [modelOptions, modelQuery]);

  const modelLabelMap = useMemo(() => {
    return new Map(modelOptions.map((opt) => [opt.key, opt.label]));
  }, [modelOptions]);

  const toggleModelSelection = (model: string) => {
    setSelectedModels((prev) => {
      if (prev.includes(model)) {
        return prev.filter((m) => m !== model);
      }
      if (prev.length >= 5) return prev;
      return [...prev, model];
    });
  };

  const comparisonData = useMemo(() => {
    if (!selectedModels.length) return [];
    return buildComparisonTable(selectedModels, benchmarks, results);
  }, [selectedModels, benchmarks, results]);

  const timeSeries = useMemo(() => {
    if (!currentBenchmark) return [];
    return buildTimeSeries(currentBenchmark, results);
  }, [currentBenchmark, results]);

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
    <div className="container-wide py-12">
      <div className="mb-8">
        <h1 className="font-serif text-display-sm text-base-900">
          Benchmark Explorer
        </h1>
        <p className="mt-2 text-body text-base-500">
          Slice, compare, and analyze benchmark performance
        </p>
      </div>

      {/* Benchmark Tabs */}
      <div className="mb-8 overflow-x-auto scrollbar-x">
        <div className="flex gap-2 pb-2 min-w-max">
          {visibleBenchmarks.map((benchmark) => (
            <button
              key={benchmark.id}
              onClick={() => setActiveBenchmark(benchmark.id)}
              className={`px-4 py-2 rounded-lg text-body-sm whitespace-nowrap transition-colors ${
                activeBenchmark === benchmark.id
                  ? "bg-accent text-base-900 font-medium"
                  : "bg-base-50 text-base-500 hover:bg-base-100 hover:text-base-700"
              }`}
            >
              {benchmark.name}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Filters */}
        <aside className="lg:col-span-3 card card-muted">
          <div className="text-caption uppercase tracking-wider text-base-500">
            Filters
          </div>
          <div className="mt-4 space-y-4">
            <label className="block">
              <span className="text-body-sm text-base-500">Search model</span>
              <input
                className="mt-2 w-full px-3 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900"
                value={filters.search}
                onChange={(e) =>
                  setFilters({ ...filters, search: e.target.value })
                }
                placeholder="e.g. gpt-5"
              />
            </label>

            <label className="block">
              <span className="text-body-sm text-base-500">Provider</span>
              <div className="mt-2 space-y-2">
                {providers.map((provider) => {
                  const active = filters.providers.includes(provider);
                  return (
                    <label
                      key={provider}
                      className="flex items-center gap-2 text-body-sm text-base-500"
                    >
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={() =>
                          setFilters({
                            ...filters,
                            providers: active
                              ? filters.providers.filter((p) => p !== provider)
                              : [...filters.providers, provider],
                          })
                        }
                      />
                      {provider}
                    </label>
                  );
                })}
              </div>
            </label>

            <label className="block">
              <span className="text-body-sm text-base-500">Category</span>
              <select
                className="mt-2 w-full px-3 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900"
                value={filters.category}
                onChange={(e) =>
                  setFilters({ ...filters, category: e.target.value })
                }
              >
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c === "all" ? "All categories" : c}
                  </option>
                ))}
              </select>
            </label>

            {currentBenchmark?.id === "metr_time_horizons" && (
              <label className="block">
                <span className="text-body-sm text-base-500">METR Version</span>
                <select
                  className="mt-2 w-full px-3 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900"
                  value={filters.metrVersion}
                  onChange={(e) =>
                    setFilters({ ...filters, metrVersion: e.target.value })
                  }
                >
                  <option value="all">All versions</option>
                  <option value="v1.1">v1.1</option>
                  <option value="v1.0">v1.0</option>
                </select>
              </label>
            )}

            <label className="block">
              <span className="text-body-sm text-base-500">Trust tier</span>
              <div className="mt-2 flex gap-2 flex-wrap">
                {["A", "B", "C"].map((tier) => (
                  <button
                    key={tier}
                    type="button"
                    className={`chip ${
                      filters.trust.includes(tier) ? "chip-accent" : ""
                    }`}
                    onClick={() =>
                      setFilters({
                        ...filters,
                        trust: filters.trust.includes(tier)
                          ? filters.trust.filter((t) => t !== tier)
                          : [...filters.trust, tier],
                      })
                    }
                  >
                    {tier}
                  </button>
                ))}
              </div>
            </label>

            <label className="block">
              <span className="text-body-sm text-base-500">Date range</span>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <input
                  type="date"
                  className="px-2 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900"
                  value={filters.startDate}
                  onChange={(e) =>
                    setFilters({ ...filters, startDate: e.target.value })
                  }
                />
                <input
                  type="date"
                  className="px-2 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900"
                  value={filters.endDate}
                  onChange={(e) =>
                    setFilters({ ...filters, endDate: e.target.value })
                  }
                />
              </div>
            </label>

            <label className="flex items-center gap-2 text-body-sm text-base-500">
              <input
                type="checkbox"
                checked={filters.onlyOfficial}
                onChange={(e) =>
                  setFilters({ ...filters, onlyOfficial: e.target.checked })
                }
              />
              Only official results (Tier A)
            </label>

            <label className="flex items-center gap-2 text-body-sm text-base-500">
              <input
                type="checkbox"
                checked={filters.normalize}
                onChange={(e) =>
                  setFilters({ ...filters, normalize: e.target.checked })
                }
              />
              Normalize scores to 0–100
            </label>
          </div>
        </aside>

        {/* Main */}
        <div className="lg:col-span-9 space-y-6">
          {currentBenchmark && (
            <div className="card">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                <div>
                  <span className="text-caption uppercase tracking-wider text-accent">
                    {CATEGORY_LABELS[currentBenchmark.category] ||
                      currentBenchmark.category}
                  </span>
                  <h2 className="font-serif text-title-lg text-base-900 mt-1">
                    {currentBenchmark.name}
                  </h2>
                  <p className="mt-2 text-body text-base-500 max-w-2xl">
                    {currentBenchmark.description}
                  </p>
                </div>
                <div className="flex gap-4">
                  {currentBenchmark.official_url && (
                    <a
                      href={currentBenchmark.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-body-sm text-accent hover:underline"
                    >
                      Official Site →
                    </a>
                  )}
                  {currentBenchmark.paper_url && (
                    <a
                      href={currentBenchmark.paper_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-body-sm text-base-500 hover:text-base-700 hover:underline"
                    >
                      Paper →
                    </a>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-base-100 flex flex-wrap gap-6 text-body-sm text-base-500">
                <div>
                  <span className="text-base-400">Scale:</span>{" "}
                  <span className="font-mono">
                    {currentBenchmark.scale.min} –{" "}
                    {currentBenchmark.scale.max != null
                      ? `${currentBenchmark.scale.max} ${currentBenchmark.unit}`
                      : "Open-ended"}
                  </span>
                </div>
                <div>
                  <span className="text-base-400">Direction:</span>{" "}
                  {currentBenchmark.higher_is_better
                    ? "Higher is better"
                    : "Lower is better"}
                </div>
                <div>
                  <span className="text-base-400">Results:</span>{" "}
                  <span className="font-mono">{benchmarkResults.length}</span>
                </div>
              </div>
            </div>
          )}

          {/* Results Table */}
          <div className="card overflow-hidden p-0">
            <table className="data-table">
              <thead>
                <tr className="bg-base-50">
                  <th className="w-12">#</th>
                  <th>Model</th>
                  <th>Provider</th>
                  <th className="text-right">
                    {filters.normalize ? "Score (0-100)" : "Score"}
                  </th>
                  <th className="text-right">Date</th>
                  {currentBenchmark?.id === "metr_time_horizons" && (
                    <th className="text-right">Version</th>
                  )}
                  <th className="text-center">Trust</th>
                </tr>
              </thead>
              <tbody>
                {benchmarkResults.map((result, index) => {
                  const displayScore =
                    filters.normalize && currentBenchmark
                      ? normalizeScore(result.score, currentBenchmark)
                      : result.score;
                  const displayUnit = filters.normalize
                    ? "percent"
                    : currentBenchmark?.unit || "percent";
                  return (
                    <tr
                      key={result.id}
                      className="group cursor-pointer"
                      onClick={() => setSelectedResult(result)}
                    >
                      <td className="font-mono text-base-400">{index + 1}</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{
                              backgroundColor:
                                PROVIDER_COLORS[result.provider] ||
                                PROVIDER_COLORS.Unknown,
                            }}
                          />
                          <span className="font-medium text-base-900">
                            {getModelLabel(result)}
                          </span>
                        </div>
                      </td>
                      <td className="text-base-500">{result.provider}</td>
                      <td className="text-right">
                        <span className="font-mono text-accent font-medium">
                          {formatScore(
                            displayScore ?? null,
                            displayUnit
                          )}
                        </span>
                        {result.score_stderr && !filters.normalize && (
                          <span className="text-base-400 text-caption ml-1">
                            ±{result.score_stderr.toFixed(2)}
                          </span>
                        )}
                      </td>
                      <td className="text-right text-base-500">
                        {formatDate(result.date)}
                      </td>
                      {currentBenchmark?.id === "metr_time_horizons" && (
                        <td className="text-right text-base-500">
                          {result.subset || "—"}
                        </td>
                      )}
                      <td className="text-center">
                        <TrustBadge tier={result.trust_tier} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {benchmarkResults.length === 0 && (
              <div className="p-12 text-center text-base-500">
                No results available for this benchmark
              </div>
            )}
          </div>

          {/* Model Comparison */}
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-serif text-title-sm text-base-900">
                  Compare Models Across Benchmarks
                </h3>
                <p className="text-body-sm text-base-500">
                  Select up to 5 models to compare normalized performance
                </p>
              </div>
              <div className="text-caption text-base-400">
                {selectedModels.length}/5 selected
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-2">
                {selectedModels.length === 0 && (
                  <span className="text-caption text-base-400">
                    No models selected yet
                  </span>
                )}
            {selectedModels.map((model) => (
                  <button
                    key={model}
                    type="button"
                    className="chip chip-strong"
                    onClick={() => toggleModelSelection(model)}
                    title="Remove model"
                  >
                    {modelLabelMap.get(model) || model}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  className="flex-1 min-w-[200px] px-3 py-2 bg-base-50 border border-base-200 rounded-lg text-base-900"
                  placeholder="Search models..."
                  value={modelQuery}
                  onChange={(e) => setModelQuery(e.target.value)}
                />
                <button
                  type="button"
                  className="px-3 py-2 rounded-lg text-body-sm bg-base-50 text-base-500 border border-base-200 hover:bg-base-100"
                  disabled={!selectedModels.length}
                  onClick={() => setSelectedModels([])}
                >
                  Clear
                </button>
              </div>

              <div className="scroll-panel max-h-48">
                {filteredModelOptions.map((model) => {
                  const selected = selectedModels.includes(model.key);
                  return (
                    <button
                      key={model.key}
                      type="button"
                      className={`w-full text-left px-3 py-2 rounded-md text-body-sm transition-colors ${
                        selected
                          ? "bg-accent/15 text-base-900 border border-accent/40"
                          : "text-base-500 hover:bg-base-100"
                      }`}
                      onClick={() => toggleModelSelection(model.key)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              selected ? "bg-accent" : "bg-base-200"
                            }`}
                          />
                          <span className="font-medium">{model.label}</span>
                        </div>
                        {selected && (
                          <span className="text-caption text-accent">
                            Selected
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
                {filteredModelOptions.length === 0 && (
                  <div className="px-3 py-3 text-body-sm text-base-400">
                    No models match that search.
                  </div>
                )}
              </div>
            </div>
            {comparisonData.length > 0 && (
              <div className="mt-4 overflow-x-auto comparison-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      {benchmarks.map((b) => (
                        <th key={b.id} className="text-center">
                          {b.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonData.map((row) => (
                      <tr key={row.model}>
                        <td className="font-medium text-base-900">{row.label}</td>
                        {row.scores.map((score, idx) => (
                          <td
                            key={`${row.model}-${idx}`}
                            className="text-center"
                            style={{
                              backgroundColor: score != null
                                ? `color-mix(in srgb, var(--color-accent) ${Math.max(
                                    score,
                                    5
                                  )}%, transparent)`
                                : "transparent",
                            }}
                          >
                            {score != null ? score.toFixed(0) : "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Change over time */}
          <div className="card">
            <h3 className="font-serif text-title-sm text-base-900">
              Top Models Over Time
            </h3>
            <div className="h-72 mt-4">
              {timeSeries.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timeSeries}>
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
                    <YAxis stroke="#71717a" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #3f3f46",
                        borderRadius: "8px",
                      }}
                      labelStyle={{ color: "#a1a1aa" }}
                      labelFormatter={(d) => formatDate(d)}
                    />
                    <Legend />
                    {Object.keys(timeSeries[0] || {})
                      .filter((k) => k !== "date")
                      .map((key) => (
                        <Line
                          key={key}
                          type="monotone"
                          dataKey={key}
                          stroke={stringToColor(key)}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-base-500">
                  Not enough data for time series
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Result Drawer */}
      {selectedResult && (
        <div
          className="fixed inset-0 flex justify-end z-50"
          style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
        >
          <div className="w-full max-w-md bg-base-50 h-full p-6 overflow-y-auto">
            <button
              onClick={() => setSelectedResult(null)}
              className="text-base-500 hover:text-base-700"
            >
              Close
            </button>
            <div className="mt-6">
              <div className="text-caption uppercase tracking-wider text-base-500">
                Result details
              </div>
              <div className="mt-2 font-serif text-title text-base-900">
                {getModelLabel(selectedResult)}
              </div>
              <div className="mt-2 text-body-sm text-base-500">
                {selectedResult.provider}
              </div>
              <div className="mt-4 space-y-2 text-body-sm text-base-500">
                <div>
                  Score:{" "}
                  <span className="font-mono text-base-900">
                    {formatScore(
                      selectedResult.score,
                      currentBenchmark?.unit || "percent"
                    )}
                  </span>
                </div>
                <div>Date: {formatDate(selectedResult.date)}</div>
                {currentBenchmark?.id === "metr_time_horizons" && (
                  <div>Version: {selectedResult.subset || "—"}</div>
                )}
                <div>
                  Trust: <TrustBadge tier={selectedResult.trust_tier} />
                </div>
                {selectedResult.source_url && (
                  <div>
                    Source:{" "}
                    <a
                      href={selectedResult.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline"
                    >
                      View source
                    </a>
                  </div>
                )}
                {selectedResult.source_type && (
                  <div>Source type: {selectedResult.source_type}</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function buildComparisonTable(
  models: string[],
  benchmarks: Benchmark[],
  results: Result[]
) {
  return models.map((model) => {
    const scores = benchmarks.map((benchmark) => {
      const record = results
        .filter(
          (r) =>
            getResultModelKey(r) === model &&
            r.benchmark_id === benchmark.id
        )
        .sort((a, b) =>
          benchmark.higher_is_better ? b.score - a.score : a.score - b.score
        )[0];
      return record ? normalizeScore(record.score, benchmark) : null;
    });
    const labelResult = results.find((r) => getResultModelKey(r) === model);
    return {
      model,
      label: labelResult ? getResultModelLabel(labelResult) : model,
      scores,
    };
  });
}

function buildTimeSeries(benchmark: Benchmark, results: Result[]) {
  const byModel = new Map<string, { label: string; rows: Result[] }>();
  results
    .filter((r) => r.benchmark_id === benchmark.id)
    .forEach((r) => {
      const key = getResultModelKey(r);
      const label = getResultModelLabel(r);
      if (!byModel.has(key)) {
        byModel.set(key, { label, rows: [] });
      }
      byModel.get(key)!.rows.push(r);
    });

  const topModels = Array.from(byModel.entries())
    .map(([model, entry]) => ({
      model,
      label: entry.label,
      best: benchmark.higher_is_better
        ? Math.max(...entry.rows.map((e) => e.score))
        : Math.min(...entry.rows.map((e) => e.score)),
    }))
    .sort((a, b) =>
      benchmark.higher_is_better ? b.best - a.best : a.best - b.best
    )
    .slice(0, 5)
    .map((m) => ({ key: m.model, label: m.label }));

  const dates = new Set<string>();
  topModels.forEach((model) => {
    byModel.get(model.key)?.rows.forEach((r) => dates.add(r.date));
  });

  const sortedDates = Array.from(dates).sort(
    (a, b) =>
      (parseDate(a)?.getTime() ?? 0) - (parseDate(b)?.getTime() ?? 0)
  );

  return sortedDates.map((date) => {
    const row: Record<string, any> = { date };
    topModels.forEach((model) => {
      const entry = byModel
        .get(model.key)
        ?.rows.find((r) => r.date === date);
      if (entry) {
        row[model.label] = entry.score;
      }
    });
    return row;
  });
}

function getResultModelLabel(result: Result) {
  return result.model_display || result.model_name;
}

function getResultModelKey(result: Result) {
  return result.model_group || getResultModelLabel(result);
}

function stringToColor(input: string) {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = input.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = hash % 360;
  return `hsl(${hue}, 60%, 55%)`;
}

export default function ExplorerPage() {
  return (
    <Suspense
      fallback={
        <div className="container-wide py-12">
          <div className="animate-pulse space-y-4">
            <div className="h-10 bg-base-50 rounded w-1/3" />
            <div className="h-96 bg-base-50 rounded" />
          </div>
        </div>
      }
    >
      <ExplorerContent />
    </Suspense>
  );
}
