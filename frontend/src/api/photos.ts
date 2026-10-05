import { api } from "./client";

export interface Photo {
  id: string;
  original_filename: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  processing_status: "pending" | "processing" | "ready" | "failed";
  is_favorite: boolean;
  created_at: string;
}

export interface PhotoMetadata {
  capture_date: string | null;
  capture_time: string | null;
  capture_date_source: string;
  latitude: number | null;
  longitude: number | null;
  location_name: string | null;
  camera_make: string | null;
  camera_model: string | null;
  caption: string | null;
  tags: string[] | null;
}

export interface DetectedObject {
  name: string;
  confidence: number;
}

export interface DetectedPerson {
  id: string;
  name: string | null;
}

export interface PhotoDetail extends Photo {
  photo_metadata: PhotoMetadata | null;
  objects: DetectedObject[];
  people: DetectedPerson[];
}

export async function fetchPhoto(id: string) {
  const res = await api.get(`/api/photos/${id}`);
  return res.data as PhotoDetail;
}

export async function setFavorite(id: string, isFavorite: boolean) {
  const res = await api.patch(`/api/photos/${id}/favorite`, null, { params: { is_favorite: isFavorite } });
  return res.data as Photo;
}

export async function fetchOriginalObjectUrl(id: string): Promise<string> {
  const res = await api.get(`/api/photos/${id}/original`, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}

export interface SemanticSearchResultItem {
  photo: Photo;
  similarity: number;
}

export async function semanticSearch(query: string, minSimilarity?: number) {
  const res = await api.post("/api/search/semantic", {
    query,
    min_similarity: minSimilarity ?? null,
    limit: 100,
  });
  return res.data as { query: string; min_similarity: number; results: SemanticSearchResultItem[] };
}

export interface HybridSearchResultItem {
  photo: Photo;
  final_score: number;
  semantic_score: number | null;
  metadata_score: number | null;
}

export interface HybridSearchFilters {
  start_date: string | null;
  end_date: string | null;
  person_name: string | null;
  object_name: string | null;
  location_name: string | null;
  semantic_query: string | null;
}

export async function hybridSearch(query: string) {
  const res = await api.post("/api/search", { query, limit: 100 });
  return res.data as { query: string; filters: HybridSearchFilters; results: HybridSearchResultItem[] };
}

export interface UploadResultItem {
  filename: string;
  status: "accepted" | "duplicate" | "rejected";
  photo_id: string | null;
  reason: string | null;
}

export async function uploadPhotos(
  files: FileList | File[], location?: { latitude: number; longitude: number; locationName?: string },
): Promise<UploadResultItem[]> {
  const form = new FormData();
  Array.from(files).forEach((file) => form.append("files", file));
  if (location) {
    form.append("latitude", String(location.latitude));
    form.append("longitude", String(location.longitude));
    if (location.locationName) form.append("location_name", location.locationName);
  }
  const res = await api.post("/api/photos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data.results;
}

export async function listPhotos(page = 1, pageSize = 50, filters?: { capture_year?: number; capture_month?: number }) {
  const res = await api.get("/api/photos", { params: { page, page_size: pageSize, ...filters } });
  return res.data as { total: number; page: number; page_size: number; items: Photo[] };
}

export async function deletePhoto(id: string) {
  await api.delete(`/api/photos/${id}`);
}

// <img src="/api/photos/x/thumbnail"> can't carry an Authorization header, so
// we fetch the bytes ourselves (through the authed axios client) and hand
// back a blob: URL the <img> tag can use instead.
export async function fetchThumbnailObjectUrl(photoId: string): Promise<string> {
  const res = await api.get(`/api/photos/${photoId}/thumbnail`, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}

export async function fetchTimeline() {
  const res = await api.get("/api/photos/timeline");
  return res.data as { year: number; month: number; count: number }[];
}

export async function reprocessPhoto(id: string) {
  await api.post(`/api/photos/${id}/reprocess`);
}
