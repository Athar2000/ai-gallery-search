import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { addPhotosToAlbum, createAlbum, listAlbums, type Album } from "../api/albums";
import { deletePhoto, listPhotos, reprocessPhoto, uploadPhotos, type Photo, type UploadResultItem } from "../api/photos";
import { Thumbnail } from "../components/Thumbnail";

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [total, setTotal] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [uploadSummary, setUploadSummary] = useState<UploadResultItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [albums, setAlbums] = useState<Album[]>([]);
  const [showAlbumPicker, setShowAlbumPicker] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    const data = await listPhotos(1, 100);
    setPhotos(data.items);
    setTotal(data.total);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // While anything is still pending/processing, poll every 2s so newly
  // uploaded photos flip to "ready" (with a real thumbnail) without a
  // manual refresh. Full background-job progress (spec section 24) would
  // need the Phase 3+ worker queue this project doesn't run standalone.
  useEffect(() => {
    const hasPending = photos.some((p) => p.processing_status === "pending" || p.processing_status === "processing");
    if (hasPending && pollRef.current === null) {
      pollRef.current = window.setInterval(refresh, 2000);
    } else if (!hasPending && pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [photos, refresh]);

  useEffect(() => {
    if (!cameraOpen) return;
    let cancelled = false;
    setCameraError(null);
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: "user" }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        cameraStreamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(() => setCameraError("Camera access was blocked. Allow camera permission and try again."));
    return () => {
      cancelled = true;
      cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    };
  }, [cameraOpen]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const results = await uploadPhotos(files);
    setUploadSummary(results);
    await refresh();
  }

  async function handleDelete(id: string) {
    await deletePhoto(id);
    await refresh();
  }

  async function handleRetry(id: string) {
    await reprocessPhoto(id);
    await refresh();
  }

  async function captureFromCamera() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      setCameraOpen(false);
      const captured = new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" });
      let location: { latitude: number; longitude: number; locationName?: string } | undefined;
      if (navigator.geolocation) {
        try {
          const position = await new Promise<GeolocationPosition>((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 }),
          );
          const { latitude, longitude } = position.coords;
          let locationName: string | undefined;
          try {
            const response = await fetch(
              `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}`,
              { headers: { Accept: "application/json" } },
            );
            if (response.ok) {
              const address = (await response.json()).address ?? {};
              locationName = [address.city, address.town, address.village, address.state, address.country]
                .filter(Boolean)
                .filter((value, index, values) => values.indexOf(value) === index)
                .join(", ");
            }
          } catch {
            // Coordinates are still saved when reverse geocoding is unavailable.
          }
          location = { latitude, longitude, locationName };
        } catch {
          // Camera upload still works when location permission is denied.
        }
      }
      setUploadSummary(await uploadPhotos([captured], location));
      await refresh();
    }, "image/jpeg", 0.92);
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(photos.filter((p) => p.processing_status === "ready").map((p) => p.id)));
  }

  async function bulkDelete() {
    await Promise.all(Array.from(selected).map((id) => deletePhoto(id)));
    setSelected(new Set());
    setSelectMode(false);
    await refresh();
  }

  async function openAlbumPicker() {
    const data = await listAlbums();
    setAlbums(data);
    setShowAlbumPicker(true);
  }

  async function addSelectedToAlbum(albumId: string) {
    await addPhotosToAlbum(albumId, Array.from(selected));
    setShowAlbumPicker(false);
    setSelected(new Set());
    setSelectMode(false);
  }

  async function createAlbumWithSelection() {
    const name = window.prompt("New album name");
    if (!name) return;
    const album = await createAlbum(name);
    await addSelectedToAlbum(album.id);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">All Photos ({total})</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setSelectMode((v) => !v);
              setSelected(new Set());
            }}
            className="rounded-lg border border-neutral-800 px-3 py-2 text-sm hover:border-neutral-600"
          >
            {selectMode ? "Cancel" : "Select"}
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 hover:bg-white"
          >
            Upload photos
          </button>
          <button
            onClick={() => setCameraOpen(true)}
            className="rounded-lg border border-neutral-800 px-3 py-2 text-sm hover:border-neutral-600"
          >
            Laptop camera
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,image/heic,image/tiff"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </header>

      {cameraOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6">
          <div className="w-full max-w-xl rounded-xl border border-neutral-800 bg-neutral-950 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Laptop camera</h2>
              <button
                onClick={() => setCameraOpen(false)}
                className="text-sm text-neutral-400 hover:text-white"
              >
                Close
              </button>
            </div>
            {cameraError ? (
              <p className="py-12 text-center text-sm text-red-400">{cameraError}</p>
            ) : (
              <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full rounded-lg bg-black object-cover" />
            )}
            <canvas ref={canvasRef} className="hidden" />
            <button
              onClick={captureFromCamera}
              disabled={Boolean(cameraError)}
              className="mt-4 w-full rounded-lg bg-neutral-100 py-2 text-sm font-medium text-neutral-900 hover:bg-white disabled:opacity-50"
            >
              Capture and upload
            </button>
          </div>
        </div>
      )}

      {selectMode && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-neutral-800 bg-neutral-900/50 p-3 text-sm">
          <span className="text-neutral-400">{selected.size} selected</span>
          <button onClick={selectAll} className="text-neutral-300 hover:underline">
            Select all
          </button>
          <button
            onClick={openAlbumPicker}
            disabled={selected.size === 0}
            className="text-neutral-300 hover:underline disabled:opacity-40"
          >
            Add to album
          </button>
          <button
            onClick={bulkDelete}
            disabled={selected.size === 0}
            className="text-red-400 hover:underline disabled:opacity-40"
          >
            Delete
          </button>
        </div>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`mb-8 rounded-xl border-2 border-dashed p-8 text-center text-sm transition ${
          dragActive ? "border-neutral-400 bg-neutral-900" : "border-neutral-800 text-neutral-500"
        }`}
      >
        Drag and drop photos here, or use the Upload button above.
      </div>

      {uploadSummary && (
        <div className="mb-6 space-y-1 rounded-lg border border-neutral-800 bg-neutral-900/50 p-3 text-sm">
          {uploadSummary.map((r, i) => (
            <div key={i} className="flex justify-between">
              <span className="text-neutral-300">{r.filename}</span>
              <span
                className={
                  r.status === "accepted"
                    ? "text-emerald-400"
                    : r.status === "duplicate"
                    ? "text-amber-400"
                    : "text-red-400"
                }
              >
                {r.status}
                {r.reason ? ` — ${r.reason}` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : photos.length === 0 ? (
        <p className="text-neutral-500">No photos yet — upload some to get started.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6">
          {photos.map((photo) => (
            <div key={photo.id} className="group relative">
              {photo.processing_status === "ready" ? (
                selectMode ? (
                  <button onClick={() => toggleSelected(photo.id)} className="block w-full">
                    <div className={selected.has(photo.id) ? "ring-2 ring-neutral-100 rounded-lg" : ""}>
                      <Thumbnail photoId={photo.id} alt={photo.original_filename} />
                    </div>
                  </button>
                ) : (
                  <Link to={`/photos/${photo.id}`}>
                    <Thumbnail photoId={photo.id} alt={photo.original_filename} />
                  </Link>
                )
              ) : (
                <div className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg bg-neutral-900 text-xs text-neutral-500">
                  {photo.processing_status === "failed" ? (
                    <>
                      <span>Failed</span>
                      <button onClick={() => handleRetry(photo.id)} className="text-neutral-300 underline">
                        Retry
                      </button>
                    </>
                  ) : (
                    "Processing…"
                  )}
                </div>
              )}
              {photo.is_favorite && <span className="absolute left-1 top-1 text-xs">★</span>}
              {!selectMode && (
                <button
                  onClick={() => handleDelete(photo.id)}
                  className="absolute right-1 top-1 hidden rounded bg-black/70 px-1.5 py-0.5 text-xs text-white group-hover:block"
                  title="Delete"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {showAlbumPicker && (
        <div
          className="fixed inset-0 flex items-center justify-center bg-black/70 p-6"
          onClick={() => setShowAlbumPicker(false)}
        >
          <div className="w-full max-w-sm rounded-xl bg-neutral-950 p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Add to album</h2>
            <div className="mb-4 space-y-1">
              {albums.map((album) => (
                <button
                  key={album.id}
                  onClick={() => addSelectedToAlbum(album.id)}
                  className="block w-full rounded-lg border border-neutral-800 px-3 py-2 text-left text-sm hover:border-neutral-600"
                >
                  {album.name} ({album.photo_count})
                </button>
              ))}
            </div>
            <button
              onClick={createAlbumWithSelection}
              className="w-full rounded-lg bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900"
            >
              + New album
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
