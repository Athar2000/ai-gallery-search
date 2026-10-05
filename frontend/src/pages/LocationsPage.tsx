import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAllLocationPhotos, listLocations, type LocationCluster } from "../api/locations";
import { Thumbnail } from "../components/Thumbnail";
import type { Photo } from "../api/photos";

export default function LocationsPage() {
  const [clusters, setClusters] = useState<LocationCluster[]>([]);
  const [locationPhotos, setLocationPhotos] = useState<Photo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listLocations(), fetchAllLocationPhotos()])
      .then(([clusterData, photoData]) => {
        setClusters(clusterData);
        setLocationPhotos(photoData.items);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← Dashboard
      </Link>
      <h1 className="mt-1 text-xl font-semibold tracking-tight">Locations</h1>
      <p className="mb-6 text-xs text-neutral-500">
        Photos grouped by saved GPS coordinates and place names.
      </p>

      {loading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : clusters.length === 0 && locationPhotos.length === 0 ? (
        <p className="text-neutral-500">No photos with location data yet.</p>
      ) : (
        <>
          <div className="mb-8 border-b border-neutral-800 pb-3">
            <h2 className="text-sm font-semibold text-neutral-200">All location photos</h2>
            <p className="mt-1 text-xs text-neutral-500">{locationPhotos.length} photos with saved location data</p>
          </div>
          <div className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6">
            {locationPhotos.map((photo) => (
              <Link key={photo.id} to={`/photos/${photo.id}`}>
                <Thumbnail photoId={photo.id} alt={photo.original_filename} />
              </Link>
            ))}
          </div>
          <h2 className="mb-3 text-sm font-semibold text-neutral-200">Location groups</h2>
          <div className="space-y-3">
            {clusters.map((c) => (
            <div key={`${c.latitude},${c.longitude}`} className="flex items-center gap-4 rounded-lg border border-neutral-800 p-3">
              <div className="w-20 shrink-0">
                <Thumbnail photoId={c.sample_photo_id} alt={c.location_name ?? "location"} />
              </div>
              <div>
                <p className="font-medium">{c.location_name ?? `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}`}</p>
                <p className="text-xs text-neutral-500">{c.photo_count} photos</p>
              </div>
            </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
