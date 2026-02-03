"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Benchmark, FrontierPoint } from "@/lib/types";
import { formatScore, formatDate } from "@/lib/data";
import { PROVIDER_COLORS, CATEGORY_LABELS } from "@/lib/types";
import { getLatestDelta } from "@/lib/analysis";
import { Sparkline } from "@/components/Sparkline";

export function BenchmarkCards() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [loading, setLoading] = useState(true);
  const [frontier, setFrontier] = useState<Record<string, FrontierPoint[]>>({});

  useEffect(() => {
    Promise.all([
      fetch("/data/benchmarks.json").then((res) => res.json()),
      fetch("/data/frontier.json").then((res) => res.json()),
    ])
      .then(([benchData, frontierData]) => {
        setBenchmarks(benchData);
        setFrontier(frontierData);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load benchmarks:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="card animate-pulse h-48 bg-base-50" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {benchmarks.map((benchmark) => (
        <BenchmarkCard
          key={benchmark.id}
          benchmark={benchmark}
          frontierPoints={frontier[benchmark.id] || []}
        />
      ))}
    </div>
  );
}

function BenchmarkCard({
  benchmark,
  frontierPoints,
}: {
  benchmark: Benchmark;
  frontierPoints: FrontierPoint[];
}) {
  const providerColor =
    PROVIDER_COLORS[benchmark.sota?.provider || "Unknown"] ||
    PROVIDER_COLORS.Unknown;
  const hasScore = benchmark.sota?.score != null;
  const delta = frontierPoints?.length ? getLatestDelta(frontierPoints) : null;
  const rawDelta = delta?.delta ?? null;
  const deltaValue =
    rawDelta != null
      ? benchmark.higher_is_better
        ? rawDelta
        : -rawDelta
      : null;

  const progress =
    hasScore &&
    benchmark.unit === "percent" &&
    benchmark.scale?.max != null
      ? clamp(
          ((benchmark.sota?.score ?? 0) - (benchmark.scale?.min ?? 0)) /
            Math.max(benchmark.scale.max - (benchmark.scale?.min ?? 0), 1),
          0,
          1
        )
      : null;

  return (
    <Link
      href={`/explorer/?benchmark=${benchmark.id}`}
      className="card group cursor-pointer hover:border-accent/50 hover:glow-accent"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-caption uppercase tracking-wider text-base-500">
              {CATEGORY_LABELS[benchmark.category] || benchmark.category}
            </span>
            {deltaValue != null && (
              <span
                className={`chip ${
                  deltaValue >= 0 ? "chip-accent" : "chip-strong"
                }`}
              >
                {deltaValue >= 0 ? "+" : ""}
                {deltaValue.toFixed(2)}
              </span>
            )}
          </div>
          <h3 className="font-serif text-title-sm text-base-900 mt-1 group-hover:text-accent transition-colors">
            {benchmark.name}
          </h3>
        </div>

        {/* Arrow icon */}
        <div className="w-8 h-8 rounded-full border border-base-200 flex items-center justify-center group-hover:border-accent group-hover:bg-accent/10 transition-colors">
          <svg
            className="w-4 h-4 text-base-400 group-hover:text-accent transition-colors"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      </div>

      {/* SOTA Score */}
      {hasScore ? (
        <div className="mb-4">
          <div className="stat-value">
            {formatScore(benchmark.sota?.score, benchmark.unit)}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: providerColor }}
            />
            <span className="text-body-sm text-base-600">
              {benchmark.sota?.model_name}
            </span>
          </div>
        </div>
      ) : (
        <div className="mb-4">
          <div className="text-body text-base-400 italic">No data yet</div>
        </div>
      )}

      {/* Sparkline */}
      {frontierPoints && frontierPoints.length > 1 && (
        <div className="mb-4">
          <Sparkline
            points={frontierPoints.slice(-12)}
            width={160}
            height={40}
            stroke="var(--color-accent)"
          />
        </div>
      )}

      {/* Progress bar */}
      {progress != null && (
        <div className="mb-4">
          <div className="h-1.5 bg-base-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-500"
              style={{
                width: `${progress * 100}%`,
              }}
            />
          </div>
          <div className="flex justify-between mt-1 text-caption text-base-400">
            <span>{benchmark.scale.min}%</span>
            <span>{benchmark.scale.max}%</span>
          </div>
        </div>
      )}

      {/* Description */}
      <p className="text-body-sm text-base-500 line-clamp-2">
        {benchmark.description}
      </p>

      {/* Date */}
      {benchmark.sota?.date && (
        <div className="mt-4 pt-4 border-t border-base-100">
          <span className="text-caption text-base-400">
            Updated {formatDate(benchmark.sota.date)}
          </span>
        </div>
      )}
    </Link>
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
