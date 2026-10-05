import { api } from "./client";
import type { Photo } from "./photos";

export interface LocationCluster {
  latitude: number;
  longitude: number;
  location_name: string | null;
  photo_count: number;
  sample_photo_id: string;
}

export async function listLocations() {
  const res = await api.get("/api/locations");
  return res.data as LocationCluster[];
}

export async function fetchAllLocationPhotos() {
  const res = await api.get("/api/locations/photos", { params: { page_size: 200 } });
  return res.data as { total: number; items: Photo[] };
}
