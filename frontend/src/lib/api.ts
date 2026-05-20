import axios, { AxiosError } from "axios";
import { useAuth } from "@/stores/auth";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 15_000,
});

// Injecter le token sur chaque requête
api.interceptors.request.use((config) => {
  const token = useAuth.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Déconnecter automatiquement sur 401
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuth.getState().logout();
      // Redirection via React Router non dispo ici — on laisse les pages gérer
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function extractErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d: any) => d.msg).join(", ");
    return error.message;
  }
  return "Erreur inconnue";
}
