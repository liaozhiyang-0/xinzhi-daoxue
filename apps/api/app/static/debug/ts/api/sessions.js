import { apiRequest, jsonBody } from "./client.js";
export function listSessions(userId) {
    return apiRequest(`/api/v1/sessions?user_id=${encodeURIComponent(userId)}`);
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
