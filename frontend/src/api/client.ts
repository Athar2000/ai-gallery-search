import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE_URL });

const ACCESS_KEY = "ai_gallery_access_token";
const REFRESH_KEY = "ai_gallery_refresh_token";

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  setAccess: (access: string) => localStorage.setItem(ACCESS_KEY, access),
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If a request fails with 401, try exactly once to refresh the access token
// using the refresh token, then retry the original request. If that also
// fails, the user is logged out.
let refreshInFlight: Promise<string | null> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = tokenStore.getRefresh();
      if (!refreshToken) {
        tokenStore.clear();
        return Promise.reject(error);
      }

      if (!refreshInFlight) {
        refreshInFlight = axios
          .post(`${API_BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken })
          .then((res) => {
            tokenStore.setAccess(res.data.access_token);
            return res.data.access_token as string;
          })
          .catch(() => {
            tokenStore.clear();
            return null;
          })
          .finally(() => {
            refreshInFlight = null;
          });
      }

      const newAccess = await refreshInFlight;
      if (newAccess) {
        originalRequest.headers.Authorization = `Bearer ${newAccess}`;
        return api(originalRequest);
      }
    }
    return Promise.reject(error);
  }
);
