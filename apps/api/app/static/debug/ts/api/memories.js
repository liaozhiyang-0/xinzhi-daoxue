import { apiRequest, jsonBody } from "./client.js";
export function listMemories(userId) {
    return apiRequest(`/api/v1/memories?user_id=${encodeURIComponent(userId)}`);
}
export function createMemory(userId, content, sourceSessionId) {
    return apiRequest("/api/v1/memories", {
        method: "POST",
        body: jsonBody({ user_id: userId, content, source_session_id: sourceSessionId || null }),
    });
}
export function updateMemory(memoryId, userId, content) {
    return apiRequest(`/api/v1/memories/${encodeURIComponent(memoryId)}`, {
        method: "PATCH",
        body: jsonBody({ user_id: userId, content }),
    });
}
export function deleteMemory(memoryId, userId) {
    return apiRequest(`/api/v1/memories/${encodeURIComponent(memoryId)}?user_id=${encodeURIComponent(userId)}`, { method: "DELETE" });
}
