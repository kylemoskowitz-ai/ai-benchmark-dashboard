"use client";

import { useMemo } from "react";
import type { FrontierPoint } from "@/lib/types";
import { parseDate } from "@/lib/data";
import { clamp } from "@/lib/analysis";

export function Sparkline({
  points,
  width = 120,
  height = 36,
  stroke = "var(--color-accent)",
  fill = "transparent",
}: {
  points: FrontierPoint[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
}) {
  const path = useMemo(() => {
    if (!points || points.length < 2) return "";
    const sorted = [...points].sort(
      (a, b) =>
        (parseDate(a.date)?.getTime() ?? 0) -
        (parseDate(b.date)?.getTime() ?? 0)
    );
    const values = sorted.map((p) => p.score).filter((v) => v != null) as number[];
    if (values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = Math.max(max - min, 1e-6);
    const step = width / (values.length - 1);
    const d = values
      .map((v, i) => {
        const x = i * step;
        const y = height - clamp((v - min) / range, 0, 1) * height;
        return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
    return d;
  }, [points, width, height]);

  if (!path) return null;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <path d={path} fill="none" stroke={stroke} strokeWidth="2" />
      {fill !== "transparent" && (
        <path
          d={`${path} L ${width} ${height} L 0 ${height} Z`}
          fill={fill}
          opacity={0.2}
        />
      )}
    </svg>
  );
}
