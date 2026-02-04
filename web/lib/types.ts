// Type definitions for benchmark data

export interface Meta {
  last_updated: string;
  generated_at: string;
  schema_version: string;
  counts: {
    benchmarks: number;
    models: number;
    results: number;
  };
}

export interface Benchmark {
  id: string;
  name: string;
  category: string;
  description: string;
  unit: string;
  scale: {
    min: number;
    max: number;
  };
  higher_is_better: boolean;
  official_url?: string;
  paper_url?: string;
  notes?: string;
  sota?: {
    score: number;
    model_id: string;
    model_name: string;
    model_display?: string;
    model_group?: string;
    model_family?: string;
    model_variant?: string;
    provider: string;
    date: string;
  };
}

export interface Model {
  id: string;
  name: string;
  display_name?: string;
  group?: string;
  provider: string;
  family?: string;
  variant?: string;
  release_date?: string;
  parameters?: number;
}

export interface Result {
  id: string;
  benchmark_id: string;
  model_id: string;
  model_name: string;
  model_display?: string;
  model_group?: string;
  model_family?: string;
  model_variant?: string;
  provider: string;
  score: number;
  score_stderr?: number;
  date: string;
  trust_tier: "A" | "B" | "C";
  source_url?: string;
  source_type?: string;
}

export interface FrontierPoint {
  date: string;
  score: number;
  model_id: string;
  model_name: string;
  model_display?: string;
  model_group?: string;
  model_family?: string;
  model_variant?: string;
  provider: string;
}

export interface ProjectionPoint {
  date: string;
  value: number;
  ci_low: number;
  ci_high: number;
}

export interface Projection {
  forecast: ProjectionPoint[];
  r_squared: number;
  points_used?: number;
}

export interface HistoryPoint {
  date: string;
  value: number;
}

export interface BenchmarkProjections {
  linear?: Projection;
  logistic?: Projection;
  power_law?: Projection;
  history?: HistoryPoint[];
}

// Provider color mapping
export const PROVIDER_COLORS: Record<string, string> = {
  OpenAI: "#10b981",
  Anthropic: "#c9a227",
  Google: "#6366f1",
  "Google DeepMind": "#6366f1",
  Meta: "#3b82f6",
  Mistral: "#f97316",
  xAI: "#8b5cf6",
  DeepSeek: "#14b8a6",
  Alibaba: "#ec4899",
  Moonshot: "#f59e0b",
  Zhipu: "#84cc16",
  Minimax: "#a855f7",
  Unknown: "#71717a",
};

// Category icons/labels
export const CATEGORY_LABELS: Record<string, string> = {
  coding: "Coding",
  reasoning: "Reasoning",
  math: "Mathematics",
  multimodal: "Multimodal",
  agents: "Agents",
  knowledge: "Knowledge",
  composite: "Composite",
};
