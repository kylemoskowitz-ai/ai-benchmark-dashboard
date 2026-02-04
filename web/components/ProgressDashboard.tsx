"use client";

import { useEffect, useMemo, useState } from "react";
import type { Benchmark, FrontierPoint, Result } from "@/lib/types";
import { formatDate, formatScore } from "@/lib/data";
import {
  computeNormalizedSlopePerYear,
  getLatestDelta,
  normalizeScore,
  summarizeTrustTiers,
} from "@/lib/analysis";
import { CategoryIcon } from "@/components/CategoryIcon";
import { Sparkline } from "@/components/Sparkline";
import { ModelStrengths } from "@/components/ModelStrengths";

type SlopeEntry = {
  benchmark: Benchmark;
  slope: number | null;
};

export function ProgressDashboard() {
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

  const slopes = useMemo(() => {
    return benchmarks.map((benchmark) => {
      const points = frontier[benchmark.id] || [];
      const slope = computeNormalizedSlopePerYear(points, benchmark);
      return { benchmark, slope };
    });
  }, [benchmarks, frontier]);

  const sortedSlopes = useMemo(() => {
    return [...slopes].sort((a, b) => (b.slope ?? -Infinity) - (a.slope ?? -Infinity));
  }, [slopes]);

  const leaders = sortedSlopes.slice(0, 4);
  const laggards = [...sortedSlopes]
    .filter((s) => s.slope != null)
    .reverse()
    .slice(0, 4);

  const latestDeltas = useMemo(() => {
    return benchmarks
      .map((b) => {
        const delta = getLatestDelta(frontier[b.id] || []);
        return { benchmark: b, delta };
      })
      .filter((d) => d.delta && d.delta.delta != null)
      .sort(
        (a, b) =>
          Math.abs(b.delta?.delta ?? 0) - Math.abs(a.delta?.delta ?? 0)
      )
      .slice(0, 4);
  }, [benchmarks, frontier]);

  const trust = useMemo(() => summarizeTrustTiers(results), [results]);

  const sotaWins = useMemo(() => {
    const counts = new Map<string, { label: string; count: number }>();
    benchmarks.forEach((b) => {
      const key =
        b.sota?.model_group ||
        b.sota?.model_display ||
        b.sota?.model_name;
      const label = b.sota?.model_display || b.sota?.model_name;
      if (!key || !label) return;
      const existing = counts.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        counts.set(key, { label, count: 1 });
      }
    });
    const top = Array.from(counts.values()).sort((a, b) => b.count - a.count)[0];
    return top ? { model: top.label, count: top.count } : null;
  }, [benchmarks]);

  if (loading) {
    return (
      <section className="container-wide py-12">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-base-50 rounded w-1/3" />
          <div className="h-64 bg-base-50 rounded" />
        </div>
      </section>
    );
  }

  return (
    <>
      <section className="container-wide py-12">
        <div className="mb-8">
          <h2 className="font-serif text-title-lg text-base-900">
            Frontier Summary
          </h2>
          <p className="mt-2 text-body text-base-500">
            Signals and velocity across benchmarks
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <SummaryCard
            title="Top Model Wins"
            value={sotaWins ? `${sotaWins.count}` : "—"}
            sub={sotaWins?.model ?? "—"}
          />
          <SummaryCard
            title="Fastest Benchmark"
            value={leaders[0]?.benchmark.name ?? "—"}
            sub={
              leaders[0]?.slope != null
                ? `${leaders[0].slope.toFixed(2)} pts/yr`
                : "—"
            }
          />
          <SummaryCard
            title="Stagnant Benchmark"
            value={laggards[0]?.benchmark.name ?? "—"}
            sub={
              laggards[0]?.slope != null
                ? `${laggards[0].slope.toFixed(2)} pts/yr`
                : "—"
            }
          />
          <SummaryCard
            title="Trust Tier A Share"
            value={
              results.length
                ? `${Math.round((trust.A / results.length) * 100)}%`
                : "—"
            }
            sub={`${trust.A} official results`}
          />
        </div>
      </section>

      <ModelStrengths />

      <section className="container-wide py-12">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="font-serif text-title-lg text-base-900">
              SOTA Highlights
            </h2>
            <p className="mt-2 text-body text-base-500">
              Biggest jumps since the last recorded SOTA
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {latestDeltas.map((item) => (
            <div key={item.benchmark.id} className="card shadow-soft">
              <div className="flex items-center gap-2 text-caption uppercase tracking-wider text-base-500">
                <CategoryIcon category={item.benchmark.category} />
                {item.benchmark.name}
              </div>
              <div className="mt-3 font-mono text-title-sm text-accent">
                {item.delta?.delta != null
                  ? (
                      item.benchmark.higher_is_better
                        ? item.delta.delta
                        : -item.delta.delta
                    ).toFixed(2)
                  : "—"}
              </div>
              <div className="text-body-sm text-base-500 mt-1">
                {item.benchmark.sota?.model_display ??
                  item.benchmark.sota?.model_name ??
                  "—"}
              </div>
              <div className="mt-4 text-caption text-base-400">
                Updated {formatDate(item.delta?.to.date || "")}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="container-wide py-12">
        <div className="mb-8">
          <h2 className="font-serif text-title-lg text-base-900">
            Trust Tier Overview
          </h2>
          <p className="mt-2 text-body text-base-500">
            Official versus verified and community data coverage
          </p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="card shadow-soft">
            <TrustDonut counts={trust} />
          </div>
          <div className="card card-muted lg:col-span-2">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <TrustStat label="Official" value={trust.A} />
              <TrustStat label="Verified" value={trust.B} />
              <TrustStat label="Community" value={trust.C} />
            </div>
          </div>
        </div>
      </section>

      <section className="container-wide py-12">
        <div className="mb-8">
          <h2 className="font-serif text-title-lg text-base-900">
            Benchmark Momentum
          </h2>
          <p className="mt-2 text-body text-base-500">
            Recent trajectories for each benchmark
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {benchmarks.map((b) => {
            const points = frontier[b.id] || [];
            const slope = computeNormalizedSlopePerYear(points, b);
            const normalized = normalizeScore(b.sota?.score, b);
            return (
              <div key={b.id} className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-caption uppercase tracking-wider text-base-500">
                      {b.category}
                    </div>
                    <div className="font-serif text-title-sm text-base-900">
                      {b.name}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-body-sm text-base-900">
                      {b.sota?.score != null
                        ? formatScore(b.sota.score, b.unit)
                        : "—"}
                    </div>
                    {normalized != null && (
                      <div className="text-caption text-base-400">
                        {normalized.toFixed(0)}% of ceiling
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-4">
                  <Sparkline points={points.slice(-12)} width={200} height={40} />
                </div>
                <div className="mt-3 text-caption text-base-400">
                  {slope != null ? `${slope.toFixed(2)} pts/yr` : "—"} · Updated{" "}
                  {formatDate(b.sota?.date || "")}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="container-wide py-12">
        <div className="mb-8">
          <h2 className="font-serif text-title-lg text-base-900">
            Leaders & Laggards
          </h2>
          <p className="mt-2 text-body text-base-500">
            Benchmarks with the fastest and slowest improvement rates
          </p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card overflow-hidden p-0">
            <div className="px-4 py-3 text-caption uppercase tracking-wider text-base-500">
              Leaders
            </div>
            <table className="data-table">
              <tbody>
                {leaders.map((entry) => (
                  <tr key={entry.benchmark.id}>
                    <td>
                      <div className="flex items-center gap-2">
                        <CategoryIcon category={entry.benchmark.category} />
                        <span className="font-medium text-base-900">
                          {entry.benchmark.name}
                        </span>
                      </div>
                    </td>
                    <td className="text-right text-base-500">
                      {entry.slope != null ? entry.slope.toFixed(2) : "—"} pts/yr
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card overflow-hidden p-0">
            <div className="px-4 py-3 text-caption uppercase tracking-wider text-base-500">
              Laggards
            </div>
            <table className="data-table">
              <tbody>
                {laggards.map((entry) => (
                  <tr key={entry.benchmark.id}>
                    <td>
                      <div className="flex items-center gap-2">
                        <CategoryIcon category={entry.benchmark.category} />
                        <span className="font-medium text-base-900">
                          {entry.benchmark.name}
                        </span>
                      </div>
                    </td>
                    <td className="text-right text-base-500">
                      {entry.slope != null ? entry.slope.toFixed(2) : "—"} pts/yr
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </>
  );
}

function SummaryCard({
  title,
  value,
  sub,
}: {
  title: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="card shadow-soft">
      <div className="text-caption uppercase tracking-wider text-base-500">
        {title}
      </div>
      <div className="mt-3 font-mono text-title-sm text-base-900">{value}</div>
      <div className="text-body-sm text-base-500 mt-1">{sub}</div>
    </div>
  );
}

function TrustDonut({ counts }: { counts: { A: number; B: number; C: number } }) {
  const total = counts.A + counts.B + counts.C;
  const values = [
    { label: "A", value: counts.A, color: "#00c758" },
    { label: "B", value: counts.B, color: "#edb200" },
    { label: "C", value: counts.C, color: "#3f3f46" },
  ];
  let start = 0;
  return (
    <div className="flex items-center gap-6">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="44" stroke="#27272a" strokeWidth="12" fill="none" />
        {values.map((slice, idx) => {
          const portion = total ? slice.value / total : 0;
          const dash = portion * 2 * Math.PI * 44;
          const gap = 2 * Math.PI * 44 - dash;
          const rotate = (start / total) * 360;
          start += slice.value;
          return (
            <circle
              key={idx}
              cx="60"
              cy="60"
              r="44"
              stroke={slice.color}
              strokeWidth="12"
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset="0"
              fill="none"
              transform={`rotate(-90 ${60} ${60}) rotate(${rotate} ${60} ${60})`}
              strokeLinecap="round"
            />
          );
        })}
      </svg>
      <div className="space-y-2 text-body-sm text-base-500">
        {values.map((slice) => (
          <div key={slice.label} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: slice.color }} />
            <span>
              {slice.label}: {slice.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrustStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-caption uppercase tracking-wider text-base-500">{label}</div>
      <div className="mt-2 font-mono text-title-sm text-base-900">{value}</div>
    </div>
  );
}
