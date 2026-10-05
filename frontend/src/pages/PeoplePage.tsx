import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAllPeoplePhotos, fetchPersonPhotos, listPeople, renamePerson, type Person } from "../api/people";
import type { Photo } from "../api/photos";
import { Thumbnail } from "../components/Thumbnail";

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [selected, setSelected] = useState<Person | null>(null);
  const [selectedPhotos, setSelectedPhotos] = useState<Photo[]>([]);
  const [allPeoplePhotos, setAllPeoplePhotos] = useState<Photo[]>([]);

  useEffect(() => {
    Promise.all([listPeople(), fetchAllPeoplePhotos()])
      .then(([peopleData, photoData]) => {
        setPeople(peopleData);
        setAllPeoplePhotos(photoData.items);
      })
      .finally(() => setLoading(false));
  }, []);

  async function saveRename(person: Person) {
    const updated = await renamePerson(person.id, draftName.trim() || "Unnamed");
    setPeople((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    setEditingId(null);
  }

  async function openPerson(person: Person) {
    setSelected(person);
    const data = await fetchPersonPhotos(person.id);
    setSelectedPhotos(data.items);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← Dashboard
      </Link>
      <h1 className="mt-1 mb-6 text-xl font-semibold tracking-tight">People</h1>

      {loading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : people.length === 0 ? (
        <p className="text-neutral-500">
          No people detected yet — they show up automatically as photos with faces are processed.
        </p>
      ) : (
        <>
          <div className="mb-8 flex items-center justify-between border-b border-neutral-800 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-neutral-200">All people photos</h2>
              <p className="mt-1 text-xs text-neutral-500">{allPeoplePhotos.length} photos with detected faces</p>
            </div>
          </div>
          <div className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6">
            {allPeoplePhotos.map((photo) => (
              <Link key={photo.id} to={`/photos/${photo.id}`}>
                <Thumbnail photoId={photo.id} alt={photo.original_filename} />
              </Link>
            ))}
          </div>
          <h2 className="mb-3 text-sm font-semibold text-neutral-200">People groups</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 md:grid-cols-6">
            {people.map((person) => (
            <div key={person.id} className="text-center">
              <button onClick={() => openPerson(person)} className="block w-full">
                {person.avatar_photo_id ? (
                  <Thumbnail photoId={person.avatar_photo_id} alt={person.name ?? "Unnamed person"} />
                ) : (
                  <div className="aspect-square rounded-lg bg-neutral-900" />
                )}
              </button>
              {editingId === person.id ? (
                <input
                  autoFocus
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  onBlur={() => saveRename(person)}
                  onKeyDown={(e) => e.key === "Enter" && saveRename(person)}
                  className="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-1 py-0.5 text-center text-xs"
                />
              ) : (
                <button
                  onClick={() => {
                    setEditingId(person.id);
                    setDraftName(person.name ?? "");
                  }}
                  className="mt-1 block w-full truncate text-xs text-neutral-300 hover:underline"
                >
                  {person.name ?? "Unnamed"}
                </button>
              )}
              <p className="text-[10px] text-neutral-600">{person.photo_count} photos</p>
            </div>
          ))}
          </div>
        </>
      )}

      {selected && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/70 p-6" onClick={() => setSelected(null)}>
          <div
            className="max-h-[80vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-neutral-950 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-4 text-lg font-semibold">{selected.name ?? "Unnamed"}</h2>
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
