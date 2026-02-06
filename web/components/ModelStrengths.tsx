"use client";

import { useEffect, useMemo, useState } from "react";
import type { Benchmark, Result } from "@/lib/types";
import { normalizeScore } from "@/lib/analysis";
import { CATEGORY_LABELS } from "@/lib/types";

type ModelStat = {
  label: string;
  totals: Record<string, { sum: number; count: number }>;
  overall: { sum: number; count: number };
};

type CategoryLeader = {
  category: string;
  best: { label: string; score: number } | null;
};

type TopModel = {
  label: string;
  overall: number;
  totals: Record<string, { sum: number; count: number }>;
  coverage: number;
};

const EXCLUDED_CATEGORIES = new Set(["impact", "economy"]);

function getAggregateIdentity(result: Result): { key: string; label: string } {
  const provider = (result.provider || "Unknown").trim();
  const family = (
    result.model_family ||
    result.model_group ||
    result.model_display ||
    result.model_name
  ).trim();
  const key = `${provider.toLowerCase()}::${family.toLowerCase()}`;
  const label = result.model_family ? `${provider} ${result.model_family}` : family;
  return { key, label };
}

export function ModelStrengths() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/results.json").then((r) => r.json()),
    ])
      .then(([benchData, resultsData]) => {
        setBenchmarks(benchData);
        setResults(resultsData);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const categories = useMemo(() => {
    const set = new Set(
      benchmarks
        .filter((b) => !EXCLUDED_CATEGORIES.has(b.category))
        .map((b) => b.category)
    );
    return Array.from(set);
  }, [benchmarks]);

  const stats = useMemo((): {
    categoryLeaders: CategoryLeader[];
    topModels: TopModel[];
  } => {
    const capabilityBenchmarks = benchmarks.filter(
      (benchmark) => !EXCLUDED_CATEGORIES.has(benchmark.category)
    );
    const byModel = new Map<string, ModelStat>();
    const dynamicRanges = new Map<string, { min: number; max: number }>();

    capabilityBenchmarks.forEach((benchmark) => {
      if (benchmark.scale?.max != null) return;
      const values = results
        .filter((r) => r.benchmark_id === benchmark.id)
        .map((r) => r.score)
        .filter((v): v is number => v != null);
      if (values.length < 2) return;
      dynamicRanges.set(benchmark.id, {
        min: Math.min(...values),
        max: Math.max(...values),
      });
    });

    capabilityBenchmarks.forEach((benchmark) => {
      const bestByModel = new Map<string, Result>();
      results
        .filter((r) => r.benchmark_id === benchmark.id)
        .forEach((r) => {
          const { key } = getAggregateIdentity(r);
          const existing = bestByModel.get(key);
          if (!existing) {
            bestByModel.set(key, r);
            return;
          }
          if (benchmark.higher_is_better) {
            if (r.score > existing.score) bestByModel.set(key, r);
          } else if (r.score < existing.score) {
            bestByModel.set(key, r);
          }
        });

      bestByModel.forEach((result) => {
        const { key, label } = getAggregateIdentity(result);
        let normalized = normalizeScore(result.score, benchmark);
        if (normalized == null) {
          const dynamic = dynamicRanges.get(benchmark.id);
          if (dynamic && dynamic.max > dynamic.min) {
            const ratio = benchmark.higher_is_better
              ? (result.score - dynamic.min) / (dynamic.max - dynamic.min)
              : (dynamic.max - result.score) / (dynamic.max - dynamic.min);
            normalized = Math.max(0, Math.min(100, ratio * 100));
          }
        }
        if (normalized == null) return;

        if (!byModel.has(key)) {
          byModel.set(key, {
            label,
            totals: {},
            overall: { sum: 0, count: 0 },
          });
        }
        const entry = byModel.get(key)!;
        if (!entry.totals[benchmark.category]) {
          entry.totals[benchmark.category] = { sum: 0, count: 0 };
        }
        entry.totals[benchmark.category].sum += normalized;
        entry.totals[benchmark.category].count += 1;
        entry.overall.sum += normalized;
        entry.overall.count += 1;
      });
    });

    const models = Array.from(byModel.values());
    const categoryLeaders: CategoryLeader[] = categories.map((category) => {
      let best: CategoryLeader["best"] = null;
      models.forEach((model) => {
        const stat = model.totals[category];
        if (!stat || stat.count === 0) return;
        const avg = stat.sum / stat.count;
        if (!best || avg > best.score) {
          best = { label: model.label, score: avg };
        }
      });
      return { category, best };
    });

    const minCategories = Math.max(2, Math.ceil(categories.length / 2));
    const rankedModels = models
      .map((model) => {
        const categoryAverages = categories.map((category) => {
          const stat = model.totals[category];
          return stat && stat.count ? stat.sum / stat.count : null;
        });
        const coverage = categoryAverages.filter((v) => v != null).length;
        const overall =
          coverage > 0
            ? categoryAverages
                .filter((v): v is number => v != null)
                .reduce((a, b) => a + b, 0) / coverage
            : 0;
        return {
          label: model.label,
          overall,
          totals: model.totals,
          coverage,
        };
      })
      .sort((a, b) => {
        if (b.coverage !== a.coverage) return b.coverage - a.coverage;
        return b.overall - a.overall;
      });

    const broadCoverage = rankedModels.filter(
      (model) => model.coverage >= minCategories
    );
    const mediumCoverage = rankedModels.filter((model) => model.coverage >= 2);
    const topModels = (
      broadCoverage.length >= 5
        ? broadCoverage
        : mediumCoverage.length
        ? mediumCoverage
        : rankedModels
    ).slice(0, 5);

    return { categoryLeaders, topModels };
  }, [benchmarks, results, categories]);

  if (loading) {
    return (
      <section className="container-wide py-12">
        <div className="card card-muted shadow-soft animate-pulse h-32" />
      </section>
    );
  }

  return (
    <section className="container-wide py-12">
      <div className="mb-8">
        <h2 className="font-serif text-title-lg text-base-900">
          Model Strengths Across Capabilities
        </h2>
        <p className="mt-2 text-body text-base-500">
          Best-performing models by capability category (normalized to 0–100)
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        {stats.categoryLeaders.map((entry) => (
          <div key={entry.category} className="card shadow-soft">
            <div className="text-caption uppercase tracking-wider text-base-500">
              {CATEGORY_LABELS[entry.category] || entry.category}
            </div>
            <div className="mt-3 font-mono text-title-sm text-accent">
              {entry.best ? entry.best.score.toFixed(1) : "—"}
            </div>
            <div className="text-body-sm text-base-500 mt-1">
              {entry.best ? entry.best.label : "No data"}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-title-sm text-base-900">
            Top Models Across Dimensions
          </h3>
          <span className="text-caption text-base-400">
            Average normalized score by category
          </span>
        </div>
        <div className="overflow-x-auto comparison-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Model</th>
                {categories.map((category) => (
                  <th key={category} className="text-center">
                    {CATEGORY_LABELS[category] || category}
                  </th>
                ))}
                <th className="text-center">Overall</th>
              </tr>
            </thead>
            <tbody>
              {stats.topModels.map((model) => (
                <tr key={model.label}>
                  <td className="font-medium text-base-900">{model.label}</td>
                  {categories.map((category) => {
                    const stat = model.totals[category];
                    const avg = stat && stat.count ? stat.sum / stat.count : null;
                    return (
                      <td key={`${model.label}-${category}`} className="text-center">
                        {avg != null ? avg.toFixed(1) : "—"}
                      </td>
                    );
                  })}
                  <td className="text-center font-mono text-accent">
                    {model.overall.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
