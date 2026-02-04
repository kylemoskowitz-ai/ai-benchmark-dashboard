"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const navItems = [
  { href: "/", label: "Progress" },
  { href: "/explorer/", label: "Explorer" },
  { href: "/projections/", label: "Projections" },
  { href: "/impact/", label: "Impact" },
];

export function Navigation() {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-base-200 bg-base/80 backdrop-blur-lg">
      <div className="container-wide">
        <nav className="flex items-center justify-between h-16">
          {/* Logo / Title */}
          <Link href="/" className="flex items-center gap-3 group">
            {/* Geometric motif - stacked bars representing progress */}
            <div className="flex items-end gap-0.5 h-6">
              <div className="w-1 h-2 bg-base-400 rounded-sm group-hover:bg-accent transition-colors" />
              <div className="w-1 h-3.5 bg-base-400 rounded-sm group-hover:bg-accent transition-colors delay-75" />
              <div className="w-1 h-5 bg-accent rounded-sm" />
              <div className="w-1 h-6 bg-accent rounded-sm" />
            </div>
            <span className="font-serif text-title-sm font-medium text-base-900">
              AI Benchmarks
            </span>
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center gap-3 sm:gap-6">
            {navItems.map((item) => {
              const isActive = mounted && (
                item.href === "/"
                  ? pathname === "/" || pathname === ""
                  : pathname?.startsWith(item.href.replace(/\/$/, ""))
              );

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link py-1 ${isActive ? "active" : ""}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      </div>
    </header>
  );
}
