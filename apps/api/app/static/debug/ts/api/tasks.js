import { apiRequest, jsonBody } from "./client.js";
export function createTask(payload) {
    return apiRequest("/api/v1/tasks", {
        method: "POST",
        body: jsonBody(payload),
    });
}
export function getTask(taskId) {
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
}
export function cancelTask(taskId) {
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/cancel`, {
        method: "POST",
        body: jsonBody({}),
    });
}
export function retryTask(taskId) {
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/retry`, {
        method: "POST",
    });
}
export function pauseTask(taskId, runtimeRunId) {
    const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/pause${query}`, { method: "POST" });
}
export function resumeTask(taskId, runtimeRunId) {
    const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/resume${query}`, { method: "POST" });
}
export function approveTask(taskId, runtimeRunId) {
    const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/approve${query}`, { method: "POST" });
}
export function submitRuntimeInput(taskId, input, runtimeRunId) {
    const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/input${query}`, {
        method: "POST",
        body: jsonBody({ input }),
    });
}
export function getTaskRuntimeControls(taskId) {
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/runtime-controls`);
}
export function listTaskEvents(taskId, after = 0) {
    return apiRequest(`/api/v1/tasks/${encodeURIComponent(taskId)}/events?after=${after}`);
}
