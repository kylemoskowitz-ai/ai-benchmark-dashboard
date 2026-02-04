"use client";

import { useEffect, useMemo, useState } from "react";
import type { Benchmark, Result } from "@/lib/types";
import { normalizeScore } from "@/lib/analysis";
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

type DiffusionPoint = {
  period: string;
  results: number;
  models: number;
};

export default function ImpactPage() {
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

  const metrics = useMemo(() => {
    const percentBenchmarks = benchmarks.filter((b) => b.unit === "percent");
    const capabilityScores = percentBenchmarks
      .map((b) =>
        b.sota ? normalizeScore(b.sota.score, b) : null
      )
      .filter((v): v is number => v != null);
    const capabilityIndex = capabilityScores.length
      ? capabilityScores.reduce((a, b) => a + b, 0) / capabilityScores.length
      : null;

    const rli = benchmarks.find((b) => b.id === "remote_labor_index");
    const impactIndex =
      rli && rli.sota ? normalizeScore(rli.sota.score, rli) : null;

    const metr = benchmarks.find((b) => b.id === "metr_time_horizons");
    const metrMinutes = metr?.sota?.score;
    const metrHours = metrMinutes != null ? metrMinutes / 60 : null;

    const now = new Date();
    const cutoff = new Date();
    cutoff.setDate(now.getDate() - 180);

    const recentResults = results.filter((r) => {
      if (!r.date) return false;
      const d = new Date(r.date);
      return d >= cutoff;
    });

    const providerBreadth = new Set(
      recentResults.map((r) => r.provider)
    ).size;

    const modelFirstSeen = new Map<string, Date>();
    results.forEach((r) => {
      if (!r.date) return;
      const key = r.model_group || r.model_display || r.model_name;
      const d = new Date(r.date);
      const existing = modelFirstSeen.get(key);
      if (!existing || d < existing) {
        modelFirstSeen.set(key, d);
      }
    });
    const newModels = Array.from(modelFirstSeen.values()).filter(
      (d) => d >= cutoff
    ).length;

    const gap =
      capabilityIndex != null && impactIndex != null
        ? capabilityIndex - impactIndex
        : null;

    return {
      capabilityIndex,
      impactIndex,
      gap,
      providerBreadth,
      newModels,
      metrHours,
    };
  }, [benchmarks, results]);

  const diffusion = useMemo<DiffusionPoint[]>(() => {
    const bucket = new Map<string, { results: number; models: Set<string> }>();

    results.forEach((r) => {
      if (!r.date) return;
      const d = new Date(r.date);
      const year = d.getFullYear();
      const quarter = Math.floor(d.getMonth() / 3) + 1;
      const key = `${year} Q${quarter}`;
      if (!bucket.has(key)) {
        bucket.set(key, { results: 0, models: new Set() });
      }
      const entry = bucket.get(key)!;
      entry.results += 1;
      entry.models.add(r.model_group || r.model_display || r.model_name);
    });

    return Array.from(bucket.entries())
      .map(([period, info]) => ({
        period,
        results: info.results,
        models: info.models.size,
      }))
      .sort((a, b) => a.period.localeCompare(b.period))
      .slice(-12);
  }, [results]);

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
    <div className="container-wide py-12 space-y-10">
      <div>
        <h1 className="font-serif text-display-sm text-base-900">
          Impact & Diffusion
        </h1>
        <p className="mt-2 text-body text-base-500">
          Proxy indicators that connect capability gains to real-world uptake.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card shadow-soft">
          <div className="text-caption uppercase tracking-wider text-base-500">
            Capability Index (Proxy)
          </div>
          <div className="mt-3 font-mono text-title-sm text-accent">
            {metrics.capabilityIndex != null
              ? metrics.capabilityIndex.toFixed(1)
              : "—"}
          </div>
          <div className="text-body-sm text-base-500 mt-1">
            Avg normalized SOTA across percent benchmarks
          </div>
        </div>
        <div className="card shadow-soft">
          <div className="text-caption uppercase tracking-wider text-base-500">
            Impact Index (Proxy)
          </div>
          <div className="mt-3 font-mono text-title-sm text-accent">
            {metrics.impactIndex != null
              ? metrics.impactIndex.toFixed(1)
              : "—"}
          </div>
          <div className="text-body-sm text-base-500 mt-1">
            Remote labor index normalized
          </div>
        </div>
        <div className="card shadow-soft">
          <div className="text-caption uppercase tracking-wider text-base-500">
            Capability–Impact Gap
          </div>
          <div className="mt-3 font-mono text-title-sm text-accent">
            {metrics.gap != null ? metrics.gap.toFixed(1) : "—"}
          </div>
          <div className="text-body-sm text-base-500 mt-1">
            Higher = impact lagging capability
          </div>
        </div>
        <div className="card shadow-soft">
          <div className="text-caption uppercase tracking-wider text-base-500">
            Autonomy Horizon
          </div>
          <div className="mt-3 font-mono text-title-sm text-accent">
            {metrics.metrHours != null
              ? `${metrics.metrHours.toFixed(1)} hrs`
              : "—"}
          </div>
          <div className="text-body-sm text-base-500 mt-1">
            METR P50 time horizon
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card shadow-soft">
          <div className="text-caption uppercase tracking-wider text-base-500">
            Deployment Breadth (180d)
          </div>
          <div className="mt-3 font-mono text-title-sm text-accent">
            {metrics.providerBreadth}
          </div>
          <div className="text-body-sm text-base-500 mt-1">
            Unique providers reporting results
          </div>
        </div>
        <div className="card shadow-soft">
          <div className="text-caption uppercase tracking-wider text-base-500">
            New Model Families (180d)
          </div>
          <div className="mt-3 font-mono text-title-sm text-accent">
            {metrics.newModels}
          </div>
          <div className="text-body-sm text-base-500 mt-1">
            First-time appearances across benchmarks
          </div>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-title text-base-900">
            Diffusion Signals Over Time
          </h2>
          <span className="text-caption text-base-400">
            Results and model families per quarter
          </span>
        </div>
        <div className="h-72">
          {diffusion.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={diffusion}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="period" stroke="#71717a" />
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
                <Line
                  type="monotone"
                  dataKey="results"
                  stroke="var(--color-accent)"
                  strokeWidth={2}
                  dot={false}
                  name="Results"
                />
                <Line
                  type="monotone"
                  dataKey="models"
                  stroke="#60a5fa"
                  strokeWidth={2}
                  dot={false}
                  name="Model families"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-base-500">
              Not enough data to compute diffusion trends.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
