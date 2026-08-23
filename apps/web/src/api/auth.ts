import type { AuthMeRead, GuestSessionRead } from "../api-types.js";
import { apiRequest } from "./client.js";

export type CurrentPrincipal = AuthMeRead | GuestSessionRead;

export function getCurrentPrincipal(): Promise<CurrentPrincipal> {
  return apiRequest<CurrentPrincipal>("/api/v1/auth/me");
}

export function createGuestSession(): Promise<GuestSessionRead> {
  return apiRequest<GuestSessionRead>("/api/v1/auth/guest", { method: "POST" });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}
