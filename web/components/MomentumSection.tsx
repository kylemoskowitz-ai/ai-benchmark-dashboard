"use client";

import { useEffect, useMemo, useState } from "react";
import type { Benchmark, FrontierPoint, Result } from "@/lib/types";
import { parseDate } from "@/lib/data";
import { computeNormalizedSlopePerYear } from "@/lib/analysis";

type SlopeEntry = {
  benchmark: Benchmark;
  slope: number | null;
};

export function MomentumSection() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [frontier, setFrontier] = useState<Record<string, FrontierPoint[]>>({});
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/frontier.json").then((r) => r.json()),
      fetch("/data/results.json").then((r) => r.json()),
    ])
      .then(([benchData, frontierData, resultsData]) => {
        setBenchmarks(benchData);
        setFrontier(frontierData);
        setResults(resultsData);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const slopes = useMemo<SlopeEntry[]>(() => {
    return benchmarks.map((benchmark) => {
      const points = frontier[benchmark.id] || [];
      const slope = computeNormalizedSlopePerYear(points, benchmark);
      return { benchmark, slope };
    });
  }, [benchmarks, frontier]);

  const medianSlope = useMemo(() => {
    const values = slopes
      .map((s) => s.slope)
      .filter((s): s is number => s != null)
      .sort((a, b) => a - b);
    if (!values.length) return null;
    const mid = Math.floor(values.length / 2);
    return values.length % 2 === 0
      ? (values[mid - 1] + values[mid]) / 2
      : values[mid];
  }, [slopes]);

  const recentUpdated = useMemo(() => {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 90);
    return benchmarks.filter((b) => {
      const date = parseDate(b.sota?.date);
      return date ? date >= cutoff : false;
    }).length;
  }, [benchmarks]);

  if (loading) {
    return (
      <section className="container-wide pt-12 pb-12">
        <div className="card card-muted shadow-soft animate-pulse h-24" />
      </section>
    );
  }

  return (
    <section className="container-wide pt-12 pb-12">
      <div className="card card-muted shadow-soft">
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6 xl:items-center">
          <div className="xl:col-span-2">
            <div className="text-caption uppercase tracking-wider text-base-500">
              Insights Since Last Update
            </div>
            <div className="mt-2 font-serif text-title text-base-900">
              Momentum across the frontier
            </div>
            <div className="text-body-sm text-base-500 mt-1">
              Median annual SOTA gain on a 0-100 normalized scale
            </div>
            <div className="mt-3 text-caption text-base-400">
              Computed from frontier trend slopes across benchmarks.
            </div>
          </div>
          <div className="xl:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-base-200 bg-base-50 px-4 py-3">
              <div className="text-caption text-base-400">
                Benchmarks updated (90d)
              </div>
              <div className="font-mono text-title-sm text-accent">
                {recentUpdated}
              </div>
            </div>
            <div className="rounded-lg border border-base-200 bg-base-50 px-4 py-3">
              <div className="text-caption text-base-400">
                Median improvement / yr
              </div>
              <div className="font-mono text-title-sm text-base-900">
                {medianSlope != null ? `${medianSlope.toFixed(2)} pts` : "—"}
              </div>
              <div className="text-caption text-base-400 mt-1">
                normalized points
              </div>
            </div>
            <div className="rounded-lg border border-base-200 bg-base-50 px-4 py-3">
              <div className="text-caption text-base-400">Total results</div>
              <div className="font-mono text-title-sm text-base-900">
                {results.length ? results.length.toLocaleString("en-US") : "—"}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
