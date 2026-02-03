"use client";

import { useEffect, useState } from "react";
import type { Meta } from "@/lib/types";

export function HeroStats() {
  const [counts, setCounts] = useState<Meta["counts"] | null>(null);

  useEffect(() => {
    fetch("/data/meta.json")
      .then((res) => (res.ok ? res.json() : Promise.reject(res.statusText)))
      .then((meta: Meta) => setCounts(meta.counts))
      .catch(() => setCounts(null));
  }, []);

  return (
    <div className="flex flex-wrap gap-8 md:gap-12">
      <StatItem value={formatCount(counts?.benchmarks)} label="Benchmarks" />
      <StatItem value={formatCount(counts?.models)} label="Models" />
      <StatItem value={formatCount(counts?.results)} label="Results" />
    </div>
  );
}

function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-mono text-display-sm font-medium text-base-900">
        {value}
      </div>
      <div className="text-body-sm text-base-500 uppercase tracking-wide">
        {label}
      </div>
    </div>
  );
}

function formatCount(value?: number): string {
  if (value == null) return "—";
  return value.toLocaleString("en-US");
}
