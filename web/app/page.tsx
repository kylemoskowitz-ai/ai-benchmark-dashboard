import { Suspense } from "react";
import { BenchmarkCards } from "@/components/BenchmarkCards";
import { HeroSection } from "@/components/HeroSection";

export default function ProgressPage() {
  return (
    <div className="animate-fade-in">
      {/* Hero Section */}
      <HeroSection />

      {/* Benchmark Cards Grid */}
      <section className="container-wide py-12">
        <div className="mb-8">
          <h2 className="font-serif text-title-lg text-base-900">
            Benchmark Overview
          </h2>
          <p className="mt-2 text-body text-base-500">
            Current state-of-the-art across key capability benchmarks
          </p>
        </div>

        <Suspense
          fallback={
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="card animate-pulse h-48 bg-base-50"
                />
              ))}
            </div>
          }
        >
          <BenchmarkCards />
        </Suspense>
      </section>
    </div>
  );
}
