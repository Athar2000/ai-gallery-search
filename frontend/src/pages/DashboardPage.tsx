import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

interface Stats {
  total_photos: number;
  photos_ready: number;
  photos_processing: number;
  total_albums: number;
  total_people: number;
}

const EXAMPLE_QUERIES = [
  "Photos from August 2025",
  "Beach photos",
  "Photos with cars",
  "Photos with Athar",
  "Photos from Lucknow",
  "Photos from my trip in 2025",
];

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.get("/api/stats").then((res) => setStats(res.data));
  }, []);

  function runSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8 flex items-end justify-between gap-6">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-lime-300">Command center</p>
          <h1 className="text-3xl font-semibold tracking-tight">Good to see you, {user?.full_name || "there"}</h1>
          <p className="mt-2 text-sm text-neutral-400">Your gallery index is ready for its next search.</p>
        </div>
        <Link to="/photos" className="rounded-md bg-lime-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-lime-200">Open library</Link>
      </header>

      <div className="mb-8 border-y border-neutral-800/80 py-6">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.14em] text-neutral-500">Search your library</p>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") runSearch(query);
          }}
          placeholder="Search your photos..."
          className="w-full rounded-md border border-neutral-700 bg-neutral-900/80 px-4 py-3 text-base outline-none transition placeholder:text-neutral-600 focus:border-lime-300"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => runSearch(q)}
              className="rounded-md border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:border-neutral-600 hover:text-neutral-200"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-200">Library health</h2>
        <span className="text-xs text-neutral-500">Live index metrics</span>
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-neutral-800 bg-neutral-800 sm:grid-cols-5">
        <StatCard label="Total photos" value={stats?.total_photos} />
        <StatCard label="Ready" value={stats?.photos_ready} />
        <StatCard label="Processing" value={stats?.photos_processing} />
        <StatCard label="Albums" value={stats?.total_albums} />
        <StatCard label="People" value={stats?.total_people} />
      </div>
      <Link to="/smart-filters" className="mt-8 flex items-center justify-between rounded-md border border-lime-300/30 bg-lime-300/5 px-4 py-3 text-sm text-lime-200 transition hover:border-lime-300/60 hover:bg-lime-300/10">
        <span><strong className="mr-2">AI vision filters</strong><span className="text-xs text-lime-100/60">Browse people, animals, objects and places</span></span>
        <span>Open ↗</span>
      </Link>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
      <p className="text-2xl font-semibold">{value ?? "–"}</p>
      <p className="text-xs text-neutral-400">{label}</p>
    </div>
  );
}
