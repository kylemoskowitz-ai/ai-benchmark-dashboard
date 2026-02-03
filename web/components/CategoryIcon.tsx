"use client";

export function CategoryIcon({ category }: { category: string }) {
  const color = "var(--color-accent)";
  switch (category) {
    case "reasoning":
      return <Circle color={color} />;
    case "math":
      return <Triangle color={color} />;
    case "coding":
      return <Square color={color} />;
    case "multimodal":
      return <Hex color={color} />;
    case "agents":
      return <Diamond color={color} />;
    default:
      return <Dot color={color} />;
  }
}

function Circle({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <circle cx="7" cy="7" r="5" fill={color} />
    </svg>
  );
}

function Triangle({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <path d="M7 2 L12 12 H2 Z" fill={color} />
    </svg>
  );
}

function Square({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <rect x="3" y="3" width="8" height="8" fill={color} />
    </svg>
  );
}

function Hex({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <path d="M7 1 L12 4.5 V9.5 L7 13 L2 9.5 V4.5 Z" fill={color} />
    </svg>
  );
}

function Diamond({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <path d="M7 1 L13 7 L7 13 L1 7 Z" fill={color} />
    </svg>
  );
}

function Dot({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <circle cx="7" cy="7" r="3" fill={color} />
    </svg>
  );
}
