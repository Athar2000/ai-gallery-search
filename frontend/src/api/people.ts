import { api } from "./client";
import type { Photo } from "./photos";

export interface Person {
  id: string;
  name: string | null;
  avatar_photo_id: string | null;
  photo_count: number;
}

export async function listPeople() {
  const res = await api.get("/api/people");
  return res.data as Person[];
}

export async function fetchAllPeoplePhotos() {
  const res = await api.get("/api/people/photos", { params: { page_size: 200 } });
  return res.data as { total: number; items: Photo[] };
}

export async function renamePerson(id: string, name: string) {
  const res = await api.patch(`/api/people/${id}`, { name });
  return res.data as Person;
}

export async function fetchPersonPhotos(id: string) {
  const res = await api.get(`/api/people/${id}/photos`, { params: { page_size: 100 } });
  return res.data as { total: number; items: Photo[] };
}
