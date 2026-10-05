import { api } from "./client";
import type { Photo } from "./photos";

export interface Album {
  id: string;
  name: string;
  description: string | null;
  cover_photo_id: string | null;
  photo_count: number;
  created_at: string;
}

export async function listAlbums() {
  const res = await api.get("/api/albums");
  return res.data as Album[];
}

export async function createAlbum(name: string) {
  const res = await api.post("/api/albums", { name });
  return res.data as Album;
}

export async function addPhotosToAlbum(albumId: string, photoIds: string[]) {
  const res = await api.post(`/api/albums/${albumId}/photos`, { photo_ids: photoIds });
  return res.data as Album;
}

export async function fetchAlbumPhotos(albumId: string) {
  const res = await api.get(`/api/albums/${albumId}/photos`, { params: { page_size: 100 } });
  return res.data as { total: number; items: Photo[] };
}

export async function deleteAlbum(albumId: string) {
  await api.delete(`/api/albums/${albumId}`);
}
