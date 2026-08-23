import type { SessionRead } from "../api-types.js";
import { apiRequest, jsonBody } from "./client.js";

export interface SessionMessage {
  id: string;
  role: string;
  content_text: string;
  content_data: Record<string, unknown>;
  sequence: number;
  status: string;
}

export interface SessionTaskHistory {
  id: string;
  course_id: string;
  intent: string;
  status: string;
  question: string;
  answer: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  [key: string]: unknown;
}

export function listSessions(userId: string): Promise<SessionRead[]> {
  return apiRequest<SessionRead[]>(
    `/api/v1/sessions?user_id=${encodeURIComponent(userId)}`,
  );
}

export function createSession(
  userId: string,
  courseId = "CT",
): Promise<SessionRead> {
  return apiRequest<SessionRead>("/api/v1/sessions", {
    method: "POST",
    body: jsonBody({ user_id: userId, course_id: courseId, title: "" }),
  });
}

export function listSessionTasks(
  sessionId: string,
  userId: string,
): Promise<SessionTaskHistory[]> {
  return apiRequest<SessionTaskHistory[]>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/tasks?user_id=${encodeURIComponent(userId)}`,
  );
}

export function listSessionMessages(
  sessionId: string,
  userId: string,
): Promise<SessionMessage[]> {
  return apiRequest<SessionMessage[]>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages?user_id=${encodeURIComponent(userId)}`,
  );
}
