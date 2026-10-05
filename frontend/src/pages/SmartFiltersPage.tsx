import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const filters = [
  { label: "People", query: "people", code: "01", tone: "lime" },
  { label: "Animal", query: "animal", code: "02", tone: "amber" },
  { label: "Fruit", query: "fruit", code: "03", tone: "rose" },
  { label: "Vehicle", query: "cars", code: "04", tone: "sky" },
  { label: "Place", query: "place", code: "05", tone: "violet" },
];

export default function SmartFiltersPage() {
  const navigate = useNavigate();
  const [active, setActive] = useState<string | null>(null);

  function applyFilter(query: string) {
    setActive(query);
    navigate(`/search?q=${encodeURIComponent(query)}`);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex items-end justify-between gap-6">
        <div>
          <Link to="/" className="text-xs text-neutral-500 hover:text-neutral-300">← Overview</Link>
          <div className="mt-4 flex items-center gap-3">
            <span className="ai-pulse">AI</span>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-lime-300">Vision index</p>
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Smart filters</h1>
          <p className="mt-2 text-sm text-neutral-400">Jump straight to what the vision model found.</p>
        </div>
            <span className="hidden text-xs text-neutral-500 sm:block">5 active classifiers</span>
      </div>

      <div className="filter-grid">
        {filters.map((filter) => (
          <button
            key={filter.query}
            onClick={() => applyFilter(filter.query)}
            className={`filter-tile tone-${filter.tone} ${active === filter.query ? "is-active" : ""}`}
          >
            <span className="filter-code">{filter.code}</span>
            <span className="filter-signal" />
            <span className="filter-label">{filter.label}</span>
            <span className="filter-action">Search matches ↗</span>
          </button>
        ))}
      </div>

      <div className="mt-10 border-t border-neutral-800/80 pt-5 text-xs text-neutral-500">
        Object matches are generated from indexed photo detections. Place matches require saved GPS or location metadata.
      </div>
    </div>
  );
}
