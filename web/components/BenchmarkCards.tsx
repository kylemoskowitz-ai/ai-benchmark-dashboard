"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Benchmark } from "@/lib/types";
import { formatScore, formatDate } from "@/lib/data";
import { PROVIDER_COLORS, CATEGORY_LABELS } from "@/lib/types";

export function BenchmarkCards() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/benchmarks.json")
      .then((res) => res.json())
      .then((data) => {
        setBenchmarks(data);
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

  // Group benchmarks by category
  const categories = new Map<string, Benchmark[]>();
  benchmarks.forEach((b) => {
    const cat = b.category || "other";
    if (!categories.has(cat)) {
      categories.set(cat, []);
    }
    categories.get(cat)!.push(b);
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {benchmarks.map((benchmark) => (
        <BenchmarkCard key={benchmark.id} benchmark={benchmark} />
      ))}
    </div>
  );
}

function BenchmarkCard({ benchmark }: { benchmark: Benchmark }) {
  const providerColor =
    PROVIDER_COLORS[benchmark.sota?.provider || "Unknown"] ||
    PROVIDER_COLORS.Unknown;

  return (
    <Link
      href={`/explorer/?benchmark=${benchmark.id}`}
      className="card group cursor-pointer hover:border-accent/50 hover:glow-accent/10"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <span className="text-caption uppercase tracking-wider text-base-500">
            {CATEGORY_LABELS[benchmark.category] || benchmark.category}
          </span>
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
      {benchmark.sota ? (
        <div className="mb-4">
          <div className="stat-value">
            {formatScore(benchmark.sota.score, benchmark.unit)}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: providerColor }}
            />
            <span className="text-body-sm text-base-600">
              {benchmark.sota.model_name}
            </span>
          </div>
        </div>
      ) : (
        <div className="mb-4">
          <div className="text-body text-base-400 italic">No data yet</div>
        </div>
      )}

      {/* Progress bar */}
      {benchmark.sota && benchmark.sota.score != null && benchmark.unit === "percent" && (
        <div className="mb-4">
          <div className="h-1.5 bg-base-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(
                  (benchmark.sota.score / benchmark.scale.max) * 100,
                  100
                )}%`,
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
