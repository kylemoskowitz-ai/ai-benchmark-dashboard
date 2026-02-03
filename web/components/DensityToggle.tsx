"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "ui_density";

export function DensityToggle() {
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");

  useEffect(() => {
    const saved =
      typeof window !== "undefined"
        ? (window.localStorage.getItem(STORAGE_KEY) as
            | "comfortable"
            | "compact"
            | null)
        : null;
    const initial = saved === "compact" ? "compact" : "comfortable";
    setDensity(initial);
    setDensityAttribute(initial);
  }, []);

  function setDensityAttribute(value: "comfortable" | "compact") {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.density =
        value === "compact" ? "compact" : "comfortable";
    }
  }

  function toggle() {
    const next = density === "compact" ? "comfortable" : "compact";
    setDensity(next);
    setDensityAttribute(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="chip chip-strong border-base-200 hover:border-accent transition-colors"
      aria-label="Toggle density"
    >
      {density === "compact" ? "Compact" : "Comfortable"}
    </button>
  );
}
