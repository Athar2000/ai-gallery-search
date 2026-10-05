import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createAlbum, fetchAlbumPhotos, listAlbums, type Album } from "../api/albums";
import type { Photo } from "../api/photos";
import { Thumbnail } from "../components/Thumbnail";

export default function AlbumsPage() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [selected, setSelected] = useState<Album | null>(null);
  const [selectedPhotos, setSelectedPhotos] = useState<Photo[]>([]);

  function refresh() {
    return listAlbums().then((data) => {
      setAlbums(data);
      setLoading(false);
    });
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    await createAlbum(newName.trim());
    setNewName("");
    await refresh();
  }

  async function openAlbum(album: Album) {
    setSelected(album);
    const data = await fetchAlbumPhotos(album.id);
    setSelectedPhotos(data.items);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← Dashboard
      </Link>
      <h1 className="mt-1 mb-6 text-xl font-semibold tracking-tight">Albums</h1>

      <form onSubmit={handleCreate} className="mb-8 flex gap-2">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New album name..."
          className="flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm outline-none focus:border-neutral-500"
        />
        <button type="submit" className="rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900">
          Create
        </button>
      </form>

      {loading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : albums.length === 0 ? (
        <p className="text-neutral-500">No albums yet — create one above.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 md:grid-cols-6">
          {albums.map((album) => (
            <button key={album.id} onClick={() => openAlbum(album)} className="text-left">
              {album.cover_photo_id ? (
                <Thumbnail photoId={album.cover_photo_id} alt={album.name} />
              ) : (
                <div className="aspect-square rounded-lg bg-neutral-900" />
              )}
              <p className="mt-1 truncate text-xs text-neutral-300">{album.name}</p>
              <p className="text-[10px] text-neutral-600">{album.photo_count} photos</p>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/70 p-6" onClick={() => setSelected(null)}>
          <div
            className="max-h-[80vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-neutral-950 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-4 text-lg font-semibold">{selected.name}</h2>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
              {selectedPhotos.map((photo) => (
                <Thumbnail key={photo.id} photoId={photo.id} alt={photo.original_filename} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
