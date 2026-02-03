// Data fetching utilities for static JSON files

import type {
  Meta,
  Benchmark,
  Model,
  Result,
  FrontierPoint,
  BenchmarkProjections,
} from "./types";

const DATA_PATH = "/data";

async function fetchJson<T>(filename: string): Promise<T> {
  const res = await fetch(`${DATA_PATH}/${filename}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${filename}: ${res.statusText}`);
  }
  return res.json();
}

export async function getMeta(): Promise<Meta> {
  return fetchJson<Meta>("meta.json");
}

export async function getBenchmarks(): Promise<Benchmark[]> {
  return fetchJson<Benchmark[]>("benchmarks.json");
}

export async function getModels(): Promise<Model[]> {
  return fetchJson<Model[]>("models.json");
}

export async function getResults(): Promise<Result[]> {
  return fetchJson<Result[]>("results.json");
}

export async function getFrontier(): Promise<Record<string, FrontierPoint[]>> {
  return fetchJson<Record<string, FrontierPoint[]>>("frontier.json");
}

export async function getProjections(): Promise<Record<string, BenchmarkProjections>> {
  return fetchJson<Record<string, BenchmarkProjections>>("projections.json");
}

// Helper to get results for a specific benchmark
export function getResultsForBenchmark(
  results: Result[],
  benchmarkId: string
): Result[] {
  return results
    .filter((r) => r.benchmark_id === benchmarkId)
    .sort((a, b) => b.score - a.score);
}

// Helper to get results for a specific model
export function getResultsForModel(
  results: Result[],
  modelId: string
): Result[] {
  return results.filter((r) => r.model_id === modelId);
}

// Format score with appropriate precision
export function formatScore(score: number | null | undefined, unit: string): string {
  if (score === null || score === undefined) {
    return "—";
  }
  if (unit === "percent") {
    return `${score.toFixed(1)}%`;
  }
  if (unit === "minutes") {
    return `${score.toFixed(1)} min`;
  }
  if (unit === "index") {
    return score.toFixed(2);
  }
  return score.toFixed(2);
}

// Format date for display
export function formatDate(dateStr: string): string {
  const date = parseDate(dateStr);
  if (!date) return "—";
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Get relative time (e.g., "2 days ago")
export function getRelativeTime(dateStr: string): string {
  const date = parseDate(dateStr);
  if (!date) return "";
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

export function parseDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  // Handle date-only strings in local time to avoid timezone shifts.
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [year, month, day] = dateStr.split("-").map(Number);
    return new Date(year, month - 1, day);
  }
  const date = new Date(dateStr);
  return Number.isNaN(date.getTime()) ? null : date;
}
