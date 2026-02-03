"use client";

import { useEffect, useState } from "react";
import { formatDate } from "@/lib/data";
import type { Meta } from "@/lib/types";

export function LastUpdated() {
  const [date, setDate] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/meta.json")
      .then((res) => (res.ok ? res.json() : Promise.reject(res.statusText)))
      .then((meta: Meta) => {
        setDate(meta.last_updated || meta.generated_at || null);
      })
      .catch(() => setDate(null));
  }, []);

  return (
    <span className="font-mono" suppressHydrationWarning>
      {date ? formatDate(date) : "—"}
    </span>
  );
}
