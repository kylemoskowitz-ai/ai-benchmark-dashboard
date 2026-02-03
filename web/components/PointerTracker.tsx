"use client";

import { useEffect } from "react";

export function PointerTracker() {
  useEffect(() => {
    const root = document.documentElement;
    const update = (event: PointerEvent) => {
      root.style.setProperty("--pointer-x", `${event.clientX}px`);
      root.style.setProperty("--pointer-y", `${event.clientY}px`);
    };

    const handleScroll = () => {
      root.style.setProperty("--scroll-y", `${window.scrollY}px`);
    };

    window.addEventListener("pointermove", update, { passive: true });
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => {
      window.removeEventListener("pointermove", update);
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  return null;
}
