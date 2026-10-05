import { api, tokenStore } from "./client";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
}

export async function register(email: string, password: string, fullName?: string) {
  const res = await api.post("/api/auth/register", { email, password, full_name: fullName || null });
  tokenStore.set(res.data.access_token, res.data.refresh_token);
}

export async function login(email: string, password: string) {
  const res = await api.post("/api/auth/login", { email, password });
  tokenStore.set(res.data.access_token, res.data.refresh_token);
}

export function logout() {
  tokenStore.clear();
}

export async function fetchCurrentUser(): Promise<User> {
  const res = await api.get("/api/auth/me");
  return res.data;
}
