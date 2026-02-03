import type { Benchmark, FrontierPoint, Result } from "@/lib/types";
import { parseDate } from "@/lib/data";

export function normalizeScore(
  score: number | null | undefined,
  benchmark: Benchmark
): number | null {
  if (score == null) return null;
  const min = benchmark.scale?.min ?? 0;
  const max = benchmark.scale?.max ?? 100;
  const range = Math.max(max - min, 1e-6);
  const raw = benchmark.higher_is_better
    ? (score - min) / range
    : (max - score) / range;
  return clamp(raw * 100, 0, 100);
}

export function computeSlopePerYear(points: FrontierPoint[]): number | null {
  if (points.length < 2) return null;
  const xs: number[] = [];
  const ys: number[] = [];
  for (const p of points) {
    const date = parseDate(p.date);
    if (!date || p.score == null) continue;
    xs.push(date.getTime());
    ys.push(p.score);
  }
  if (xs.length < 2) return null;
  const { slope } = linearRegression(xs, ys);
  const msPerYear = 365.25 * 24 * 60 * 60 * 1000;
  return slope * msPerYear;
}

export function computeNormalizedSlopePerYear(
  points: FrontierPoint[],
  benchmark: Benchmark
): number | null {
  if (points.length < 2) return null;
  const xs: number[] = [];
  const ys: number[] = [];
  for (const p of points) {
    const date = parseDate(p.date);
    if (!date || p.score == null) continue;
    const normalized = normalizeScore(p.score, benchmark);
    if (normalized == null) continue;
    xs.push(date.getTime());
    ys.push(normalized);
  }
  if (xs.length < 2) return null;
  const { slope } = linearRegression(xs, ys);
  const msPerYear = 365.25 * 24 * 60 * 60 * 1000;
  return slope * msPerYear;
}

export function linearRegression(xs: number[], ys: number[]) {
  const n = xs.length;
  const xMean = xs.reduce((a, b) => a + b, 0) / n;
  const yMean = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0;
  let den = 0;
  let ssTot = 0;
  let ssRes = 0;
  for (let i = 0; i < n; i += 1) {
    const dx = xs[i] - xMean;
    const dy = ys[i] - yMean;
    num += dx * dy;
    den += dx * dx;
  }
  const slope = den === 0 ? 0 : num / den;
  const intercept = yMean - slope * xMean;
  for (let i = 0; i < n; i += 1) {
    const predicted = slope * xs[i] + intercept;
    ssTot += (ys[i] - yMean) ** 2;
    ssRes += (ys[i] - predicted) ** 2;
  }
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;
  return { slope, intercept, r2, ssTot };
}

export function estimateMaeFromR2(
  points: FrontierPoint[],
  r2: number | undefined | null
): number | null {
  if (r2 == null || points.length < 2) return null;
  const ys = points.map((p) => p.score).filter((v) => v != null) as number[];
  if (ys.length < 2) return null;
  const yMean = ys.reduce((a, b) => a + b, 0) / ys.length;
  const ssTot = ys.reduce((sum, y) => sum + (y - yMean) ** 2, 0);
  const ssRes = (1 - r2) * ssTot;
  const rmse = Math.sqrt(ssRes / ys.length);
  return rmse * 0.8;
}

export function getRecentPoints(
  points: FrontierPoint[],
  months: number
): FrontierPoint[] {
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - months);
  return points.filter((p) => {
    const d = parseDate(p.date);
    return d ? d >= cutoff : false;
  });
}

export function getLatestDelta(points: FrontierPoint[]) {
  if (points.length < 2) return null;
  const sorted = [...points].sort(
    (a, b) =>
      (parseDate(a.date)?.getTime() ?? 0) -
      (parseDate(b.date)?.getTime() ?? 0)
  );
  const last = sorted[sorted.length - 1];
  const prev = sorted[sorted.length - 2];
  if (last.score == null || prev.score == null) return null;
  return {
    delta: last.score - prev.score,
    from: prev,
    to: last,
  };
}

export function summarizeTrustTiers(results: Result[]) {
  const counts = { A: 0, B: 0, C: 0 };
  for (const r of results) {
    if (r.trust_tier === "A") counts.A += 1;
    else if (r.trust_tier === "B") counts.B += 1;
    else counts.C += 1;
  }
  return counts;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
