"use client";

export function TrustBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    A: "bg-green-500/20 text-green-400",
    B: "bg-yellow-500/20 text-yellow-400",
    C: "bg-base-200 text-base-500",
  };

  const labels: Record<string, string> = {
    A: "Official",
    B: "Verified",
    C: "Community",
  };

  return (
    <span
      className={`px-2 py-0.5 rounded text-caption font-medium ${
        colors[tier] || colors.C
      }`}
    >
      {labels[tier] || tier}
    </span>
  );
}
