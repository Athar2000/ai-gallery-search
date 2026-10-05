import { api } from "./client";

export async function deleteAllData() {
  const res = await api.post("/api/settings/delete-all-data");
  return res.data as { deleted_photos: number };
}
