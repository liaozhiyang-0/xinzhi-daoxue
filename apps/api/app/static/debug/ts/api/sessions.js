import { apiRequest, jsonBody } from "./client.js";
export function listSessions(userId, includeArchived = false) {
    return apiRequest(`/api/v1/sessions?user_id=${encodeURIComponent(userId)}&include_archived=${includeArchived}`);
}
export function searchSessions(userId, query, includeArchived = false) {
    return apiRequest(`/api/v1/sessions/search?user_id=${encodeURIComponent(userId)}&q=${encodeURIComponent(query)}&include_archived=${includeArchived}`);
}
export function createSession(userId, courseId = "CT") {
    return apiRequest("/api/v1/sessions", {
        method: "POST",
        body: jsonBody({ user_id: userId, course_id: courseId, title: "" }),
    });
}
export function listSessionTasks(sessionId, userId) {
    return apiRequest(`/api/v1/sessions/${encodeURIComponent(sessionId)}/tasks?user_id=${encodeURIComponent(userId)}`);
}
export function listSessionMessages(sessionId, userId) {
    return apiRequest(`/api/v1/sessions/${encodeURIComponent(sessionId)}/messages?user_id=${encodeURIComponent(userId)}`);
}
export function updateSession(sessionId, data) {
    return apiRequest(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
        method: "PATCH",
        body: jsonBody(data),
    });
}
export function archiveSession(sessionId, userId) {
    return apiRequest(`/api/v1/sessions/${encodeURIComponent(sessionId)}/archive?user_id=${encodeURIComponent(userId)}`, { method: "POST" });
}
export function restoreSession(sessionId, userId) {
    return apiRequest(`/api/v1/sessions/${encodeURIComponent(sessionId)}/restore?user_id=${encodeURIComponent(userId)}`, { method: "POST" });
}
export function getSessionSummary(sessionId, userId) {
    return apiRequest(`/api/v1/sessions/${encodeURIComponent(sessionId)}/summary?user_id=${encodeURIComponent(userId)}`);
}
