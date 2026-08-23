import { apiRequest, jsonBody } from "./client.js";
export function submitFeedback(data) {
    return apiRequest("/api/v1/feedback", { method: "POST", body: jsonBody(data) });
}
