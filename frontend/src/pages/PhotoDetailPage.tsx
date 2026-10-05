import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  deletePhoto,
  fetchOriginalObjectUrl,
  fetchPhoto,
  setFavorite,
  type PhotoDetail,
} from "../api/photos";

export default function PhotoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [photo, setPhoto] = useState<PhotoDetail | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    let objectUrl: string | null = null;
    setLoading(true);
    Promise.all([fetchPhoto(id), fetchOriginalObjectUrl(id)]).then(([detail, url]) => {
      setPhoto(detail);
      objectUrl = url;
      setImageUrl(url);
      setLoading(false);
    });
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  async function toggleFavorite() {
    if (!photo) return;
    const updated = await setFavorite(photo.id, !photo.is_favorite);
    setPhoto({ ...photo, is_favorite: updated.is_favorite });
  }

  async function handleDelete() {
    if (!photo) return;
    await deletePhoto(photo.id);
    navigate("/photos", { replace: true });
  }

  if (loading || !photo) {
    return <div className="p-10 text-neutral-500">Loading…</div>;
  }

  const meta = photo.photo_metadata;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <Link to="/photos" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← All Photos
      </Link>

      <div className="mt-4 grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2">
          {imageUrl && (
            <img src={imageUrl} alt={photo.original_filename} className="w-full rounded-xl object-contain" />
          )}
        </div>

        <div className="space-y-4 text-sm">
          <div className="flex gap-2">
            <button
              onClick={toggleFavorite}
              className="rounded-lg border border-neutral-800 px-3 py-1.5 hover:border-neutral-600"
            >
              {photo.is_favorite ? "★ Favorited" : "☆ Favorite"}
            </button>
            <a
              href={imageUrl ?? undefined}
              download={photo.original_filename}
              className="rounded-lg border border-neutral-800 px-3 py-1.5 hover:border-neutral-600"
            >
              Download
            </a>
            <button
              onClick={handleDelete}
              className="rounded-lg border border-red-900 px-3 py-1.5 text-red-400 hover:border-red-700"
            >
              Delete
            </button>
          </div>

          <div>
            <h2 className="mb-1 text-neutral-400">Filename</h2>
            <p>{photo.original_filename}</p>
          </div>

          {meta?.capture_date && (
            <div>
              <h2 className="mb-1 text-neutral-400">Date</h2>
              <p>
                {meta.capture_date} {meta.capture_time?.slice(0, 5)}
              </p>
            </div>
          )}

          {(meta?.camera_make || meta?.camera_model) && (
            <div>
              <h2 className="mb-1 text-neutral-400">Camera</h2>
              <p>{[meta.camera_make, meta.camera_model].filter(Boolean).join(" ")}</p>
            </div>
          )}

          {meta?.latitude != null && meta?.longitude != null && (
            <div>
              <h2 className="mb-1 text-neutral-400">Location</h2>
              <p>
                {meta.location_name ?? `${meta.latitude.toFixed(4)}, ${meta.longitude.toFixed(4)}`}
              </p>
            </div>
          )}

          {meta?.caption && (
            <div>
              <h2 className="mb-1 text-neutral-400">Description</h2>
              <p>{meta.caption}</p>
            </div>
          )}

          {photo.people.length > 0 && (
            <div>
              <h2 className="mb-1 text-neutral-400">People</h2>
              <p>{photo.people.map((p) => p.name ?? "Unnamed").join(", ")}</p>
            </div>
          )}

          {photo.objects.length > 0 && (
            <div>
              <h2 className="mb-1 text-neutral-400">Objects</h2>
              <div className="flex flex-wrap gap-1">
                {photo.objects.map((o) => (
                  <span key={o.name} className="rounded-full border border-neutral-800 px-2 py-0.5 text-xs">
                    {o.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
