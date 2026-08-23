import { apiRequest } from "./client.js";
export function getCurrentPrincipal() {
    return apiRequest("/api/v1/auth/me");
}
export function createGuestSession() {
    return apiRequest("/api/v1/auth/guest", { method: "POST" });
}
export function logout() {
    return apiRequest("/api/v1/auth/logout", { method: "POST" });
}
