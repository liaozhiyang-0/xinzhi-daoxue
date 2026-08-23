import { apiRequest, jsonBody } from "./client.js";
export function submitLearningAction(payload) {
    return apiRequest("/api/v1/learning/actions", {
        method: "POST",
        body: jsonBody(payload),
    });
}
