import { useEffect, useState } from "react";
import { fetchThumbnailObjectUrl } from "../api/photos";

export function Thumbnail({ photoId, alt }: { photoId: string; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    fetchThumbnailObjectUrl(photoId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => setFailed(true));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [photoId]);

  if (failed) {
    return (
      <div className="flex aspect-square items-center justify-center rounded-lg bg-neutral-900 text-xs text-neutral-500">
        Processing…
      </div>
    );
  }

  if (!src) {
    return <div className="aspect-square animate-pulse rounded-lg bg-neutral-900" />;
  }

  return <img src={src} alt={alt} className="aspect-square w-full rounded-lg object-cover" />;
}
