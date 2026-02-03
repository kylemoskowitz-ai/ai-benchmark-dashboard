"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { Benchmark, Result } from "@/lib/types";
import { formatScore, formatDate } from "@/lib/data";
import { PROVIDER_COLORS, CATEGORY_LABELS } from "@/lib/types";

function ExplorerContent() {
  const searchParams = useSearchParams();
  const selectedBenchmark = searchParams.get("benchmark");

  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [activeBenchmark, setActiveBenchmark] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/results.json").then((r) => r.json()),
    ])
      .then(([benchData, resultsData]) => {
        setBenchmarks(benchData);
        setResults(resultsData);
        // Set initial benchmark from URL or first one
        setActiveBenchmark(
          selectedBenchmark || (benchData[0]?.id ?? null)
        );
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load data:", err);
        setLoading(false);
      });
  }, [selectedBenchmark]);

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

  const currentBenchmark = benchmarks.find((b) => b.id === activeBenchmark);
  const benchmarkResults = results
    .filter((r) => r.benchmark_id === activeBenchmark)
    .sort((a, b) => {
      // Sort by score (higher first for higher_is_better, lower first otherwise)
      const higherIsBetter = currentBenchmark?.higher_is_better ?? true;
      return higherIsBetter ? b.score - a.score : a.score - b.score;
    });

  return (
    <div className="container-wide py-12">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-display-sm text-base-900">
          Benchmark Explorer
        </h1>
        <p className="mt-2 text-body text-base-500">
          Detailed results and rankings across all tracked benchmarks
        </p>
      </div>

      {/* Benchmark Tabs */}
      <div className="mb-8 overflow-x-auto scrollbar-hide">
        <div className="flex gap-2 pb-2">
          {benchmarks.map((benchmark) => (
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

      {/* Benchmark Info */}
      {currentBenchmark && (
        <div className="card mb-8">
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

          {/* Scale info */}
          <div className="mt-4 pt-4 border-t border-base-100 flex gap-6 text-body-sm text-base-500">
            <div>
              <span className="text-base-400">Scale:</span>{" "}
              <span className="font-mono">
                {currentBenchmark.scale.min} – {currentBenchmark.scale.max}{" "}
                {currentBenchmark.unit}
              </span>
            </div>
            <div>
              <span className="text-base-400">Direction:</span>{" "}
              {currentBenchmark.higher_is_better ? "Higher is better" : "Lower is better"}
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
              <th className="text-right">Score</th>
              <th className="text-right">Date</th>
              <th className="text-center">Trust</th>
            </tr>
          </thead>
          <tbody>
            {benchmarkResults.map((result, index) => (
              <tr key={result.id} className="group">
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
                      {result.model_name}
                    </span>
                  </div>
                </td>
                <td className="text-base-500">{result.provider}</td>
                <td className="text-right">
                  <span className="font-mono text-accent font-medium">
                    {formatScore(
                      result.score,
                      currentBenchmark?.unit || "percent"
                    )}
                  </span>
                  {result.score_stderr && (
                    <span className="text-base-400 text-caption ml-1">
                      ±{result.score_stderr.toFixed(2)}
                    </span>
                  )}
                </td>
                <td className="text-right text-base-500">
                  {formatDate(result.date)}
                </td>
                <td className="text-center">
                  <TrustBadge tier={result.trust_tier} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {benchmarkResults.length === 0 && (
          <div className="p-12 text-center text-base-500">
            No results available for this benchmark
          </div>
        )}
      </div>
    </div>
  );
}

function TrustBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    A: "bg-green-500/20 text-green-400",
    B: "bg-yellow-500/20 text-yellow-400",
    C: "bg-base-200 text-base-500",
  };

  const labels: Record<string, string> = {
    A: "Official",
    B: "Verified",
    C: "Community",
  };

  return (
    <span
      className={`px-2 py-0.5 rounded text-caption font-medium ${
        colors[tier] || colors.C
      }`}
    >
      {labels[tier] || tier}
    </span>
  );
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
