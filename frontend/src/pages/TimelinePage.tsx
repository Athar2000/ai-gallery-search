import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchTimeline } from "../api/photos";
import { fetchPhoto, listPhotos, type PhotoDetail } from "../api/photos";
import { Thumbnail } from "../components/Thumbnail";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function TimelinePage() {
  const [entries, setEntries] = useState<{ year: number; month: number; count: number }[]>([]);
  const [selected, setSelected] = useState<{ year: number; month: number } | null>(null);
  const [photos, setPhotos] = useState<PhotoDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTimeline()
      .then((data) => {
        setEntries(data);
        if (data.length > 0) selectMonth(data[0].year, data[0].month);
      })
      .finally(() => setLoading(false));
  }, []);

  function selectMonth(year: number, month: number) {
    setSelected({ year, month });
    listPhotos(1, 100, { capture_year: year, capture_month: month })
      .then((data) => Promise.all(data.items.map((photo) => fetchPhoto(photo.id))))
      .then(setPhotos);
  }

  const byYear = entries.reduce<Record<number, { month: number; count: number }[]>>((acc, e) => {
    (acc[e.year] ??= []).push({ month: e.month, count: e.count });
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← Dashboard
      </Link>
      <h1 className="mt-1 mb-6 text-xl font-semibold tracking-tight">Timeline</h1>

      {loading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-neutral-500">No dated photos yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
          <div className="space-y-4 md:col-span-1">
            {Object.entries(byYear)
              .sort(([a], [b]) => Number(b) - Number(a))
              .map(([year, months]) => (
                <div key={year}>
                  <p className="mb-1 text-sm font-semibold text-neutral-300">{year}</p>
                  <ul className="space-y-0.5 pl-2">
                    {months.map(({ month, count }) => (
                      <li key={month}>
                        <button
                          onClick={() => selectMonth(Number(year), month)}
                          className={`text-xs hover:text-neutral-100 ${
                            selected?.year === Number(year) && selected?.month === month
                              ? "text-neutral-100"
                              : "text-neutral-500"
                          }`}
                        >
                          {MONTH_NAMES[month - 1]} ({count})
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
          </div>

          <div className="md:col-span-3">
            {selected && (
              <h2 className="mb-3 text-sm text-neutral-400">
                {MONTH_NAMES[selected.month - 1]} {selected.year}
              </h2>
            )}
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {photos.map((photo) => (
                <Link key={photo.id} to={`/photos/${photo.id}`} className="block">
                  <Thumbnail photoId={photo.id} alt={photo.original_filename} />
                  <p className="mt-1 text-xs text-neutral-500">
                    {photo.photo_metadata?.capture_time
                      ? photo.photo_metadata.capture_time.slice(0, 5)
                      : new Date(photo.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
