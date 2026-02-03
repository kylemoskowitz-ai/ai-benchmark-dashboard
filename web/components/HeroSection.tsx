import { HeroStats } from "@/components/HeroStats";
import { HeroTrend } from "@/components/HeroTrend";

export function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      {/* Subtle gradient background */}
      <div className="absolute inset-0 bg-gradient-subtle" />

      {/* Decorative grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(to right, #fff 1px, transparent 1px),
                           linear-gradient(to bottom, #fff 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative container-wide py-16 md:py-24">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
          <div className="lg:col-span-3">
          {/* Eyebrow */}
          <div className="flex items-center gap-2 mb-4">
            <div className="h-px w-8 bg-accent" />
            <span className="text-caption uppercase tracking-wider text-accent font-medium">
              Frontier AI Progress
            </span>
          </div>

          {/* Main heading */}
          <h1 className="font-serif text-display text-base-900 mb-6">
            Tracking the cutting edge of
            <br />
            <span className="text-accent">artificial intelligence</span>
          </h1>

          {/* Description */}
          <p className="text-body-lg text-base-500 mb-8 max-w-2xl">
            A curated dashboard of benchmark results from leading AI labs.
            Monitoring capabilities in coding, reasoning, mathematics, and
            real-world task completion.
          </p>

          {/* Quick stats */}
          <HeroStats />
          </div>

          {/* Trend card */}
          <div className="lg:col-span-2">
            <HeroTrend />
          </div>
        </div>

        {/* Decorative element - ascending bars */}
        <div className="absolute right-8 bottom-8 hidden lg:flex items-end gap-2 opacity-20">
          {[20, 35, 45, 60, 75, 85, 95].map((h, i) => (
            <div
              key={i}
              className="w-3 bg-accent rounded-t"
              style={{ height: `${h}px` }}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
