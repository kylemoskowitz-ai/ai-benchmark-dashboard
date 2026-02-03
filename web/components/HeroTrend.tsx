"use client";

import { useEffect, useMemo, useState } from "react";
import type { Benchmark, FrontierPoint } from "@/lib/types";
import { normalizeScore } from "@/lib/analysis";
import { parseDate } from "@/lib/data";
import { Sparkline } from "@/components/Sparkline";

type TrendPoint = { date: string; score: number };

export function HeroTrend() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [frontier, setFrontier] = useState<Record<string, FrontierPoint[]>>({});

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((r) => r.json()),
      fetch("/data/frontier.json").then((r) => r.json()),
    ])
      .then(([benchData, frontierData]) => {
        setBenchmarks(benchData);
        setFrontier(frontierData);
      })
      .catch(() => {
        setBenchmarks([]);
        setFrontier({});
      });
  }, []);

  const percentBenchmarks = useMemo(
    () => benchmarks.filter((b) => b.unit === "percent"),
    [benchmarks]
  );

  const trend = useMemo(() => {
    const included = percentBenchmarks;
    if (!included.length) return [];
    if (!benchmarks.length) return [];
    const byId = new Map(included.map((b) => [b.id, b]));
    const allDates = new Set<string>();
    Object.values(frontier).forEach((points) => {
      points.forEach((p) => {
        if (p.date) allDates.add(p.date);
      });
    });
    const sortedDates = Array.from(allDates).sort(
      (a, b) =>
        (parseDate(a)?.getTime() ?? 0) - (parseDate(b)?.getTime() ?? 0)
    );

    const latest: Record<string, number> = {};
    const result: TrendPoint[] = [];

    for (const date of sortedDates) {
      for (const [benchmarkId, points] of Object.entries(frontier)) {
        if (!byId.has(benchmarkId)) continue;
        const point = points.find((p) => p.date === date);
        if (point && point.score != null) {
          latest[benchmarkId] = point.score;
        }
      }
      const normalized: number[] = [];
      for (const [benchmarkId, score] of Object.entries(latest)) {
        const benchmark = byId.get(benchmarkId);
        if (!benchmark) continue;
        const value = normalizeScore(score, benchmark);
        if (value != null) normalized.push(value);
      }
      if (normalized.length > 0) {
        const avg =
          normalized.reduce((a, b) => a + b, 0) / normalized.length;
        result.push({ date, score: avg });
      }
    }
    return result.slice(-24);
  }, [benchmarks, frontier, percentBenchmarks]);

  const latest = trend[trend.length - 1]?.score;
  const includedCount = percentBenchmarks.length;
  const subtitle = includedCount
    ? `Avg SOTA as % of benchmark max (${includedCount} benchmarks)`
    : "Avg SOTA as % of benchmark max";

  return (
    <div className="card card-muted shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-caption uppercase tracking-wider text-base-500">
            Frontier Index
          </div>
          <div className="mt-2 font-mono text-title-lg text-base-900">
            {latest != null ? `${latest.toFixed(1)}%` : "—"}
          </div>
          <div className="text-body-sm text-base-500 mt-1">{subtitle}</div>
          <div className="text-caption text-base-400 mt-1">
            100 = benchmark ceiling
          </div>
        </div>
        <div className="opacity-80">
          <Sparkline
            points={trend.map((t) => ({
              date: t.date,
              score: t.score,
              model_id: "",
              model_name: "",
              provider: "",
            }))}
            width={140}
            height={48}
            stroke="var(--color-accent)"
          />
        </div>
      </div>
    </div>
  );
}
