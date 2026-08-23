import type { FeedbackRead } from "../api-types.js";
import { apiRequest, jsonBody } from "./client.js";

export interface FeedbackInput {
  task_id: string;
  resolved?: boolean | null;
  satisfaction?: "satisfied" | "neutral" | "unsatisfied" | null;
  problem_type?: string | null;
  manual_review_required?: boolean;
  comment?: string;
}

export function submitFeedback(data: FeedbackInput): Promise<FeedbackRead> {
  return apiRequest<FeedbackRead>("/api/v1/feedback", { method: "POST", body: jsonBody(data) });
}
