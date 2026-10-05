import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { hybridSearch, type HybridSearchFilters, type HybridSearchResultItem } from "../api/photos";
import { Thumbnail } from "../components/Thumbnail";

export default function SearchResultsPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const [results, setResults] = useState<HybridSearchResultItem[]>([]);
  const [filters, setFilters] = useState<HybridSearchFilters | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) return;
    setLoading(true);
    setError(null);
    hybridSearch(query)
      .then((data) => {
        setResults(data.results);
        setFilters(data.filters);
      })
      .catch(() => setError("Search failed. Please try again."))
      .finally(() => setLoading(false));
  }, [query]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← Dashboard
      </Link>
      <h1 className="mt-1 text-xl font-semibold tracking-tight">
        {loading ? "Searching…" : `${results.length} photos found for "${query}"`}
      </h1>

      {filters && (filters.start_date || filters.semantic_query) && (
        <div className="mt-3 mb-6 flex flex-wrap gap-2">
          {filters.start_date && (
            <span className="rounded-full border border-neutral-800 px-3 py-1 text-xs text-neutral-400">
              📅 {filters.start_date === filters.end_date ? filters.start_date : `${filters.start_date} – ${filters.end_date}`}
            </span>
          )}
          {filters.semantic_query && (
            <span className="rounded-full border border-neutral-800 px-3 py-1 text-xs text-neutral-400">
              🔍 "{filters.semantic_query}"
            </span>
          )}
        </div>
      )}

      {error && <p className="mt-4 text-red-400">{error}</p>}

      {!loading && !error && results.length === 0 && (
        <p className="mt-4 text-neutral-500">No matching photos yet.</p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {results.map(({ photo, final_score }) => (
          <div key={photo.id}>
            <Thumbnail photoId={photo.id} alt={photo.original_filename} />
            <p className="mt-1 text-center text-[10px] text-neutral-500">{(final_score * 100).toFixed(0)}% match</p>
          </div>
        ))}
      </div>
    </div>
  );
}
