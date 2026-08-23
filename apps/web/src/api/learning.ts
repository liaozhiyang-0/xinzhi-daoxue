import { apiRequest, jsonBody } from "./client.js";

export interface LearningActionPayload {
  source_task_id: string;
  action: string;
  user_id: string;
  [key: string]: unknown;
}

export function submitLearningAction(payload: LearningActionPayload) {
  return apiRequest<Record<string, unknown>>("/api/v1/learning/actions", {
    method: "POST",
    body: jsonBody(payload),
  });
}
