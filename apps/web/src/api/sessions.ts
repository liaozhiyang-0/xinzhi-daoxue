import type { SessionRead, SessionSummaryRead } from "../api-types.js";
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

export interface SessionUpdate {
  user_id: string;
  title?: string | null;
  course_id?: string | null;
  memory_enabled?: boolean | null;
  auto_memory_enabled?: boolean | null;
  context_compaction_enabled?: boolean | null;
}

export function listSessions(userId: string, includeArchived = false): Promise<SessionRead[]> {
  return apiRequest<SessionRead[]>(
    `/api/v1/sessions?user_id=${encodeURIComponent(userId)}&include_archived=${includeArchived}`,
  );
}

export function searchSessions(userId: string, query: string, includeArchived = false): Promise<SessionRead[]> {
  return apiRequest<SessionRead[]>(
    `/api/v1/sessions/search?user_id=${encodeURIComponent(userId)}&q=${encodeURIComponent(query)}&include_archived=${includeArchived}`,
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

export function updateSession(sessionId: string, data: SessionUpdate): Promise<SessionRead> {
  return apiRequest<SessionRead>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    body: jsonBody(data),
  });
}

export function archiveSession(sessionId: string, userId: string): Promise<SessionRead> {
  return apiRequest<SessionRead>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/archive?user_id=${encodeURIComponent(userId)}`, { method: "POST" });
}

export function restoreSession(sessionId: string, userId: string): Promise<SessionRead> {
  return apiRequest<SessionRead>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/restore?user_id=${encodeURIComponent(userId)}`, { method: "POST" });
}

export function getSessionSummary(sessionId: string, userId: string): Promise<SessionSummaryRead | null> {
  return apiRequest<SessionSummaryRead | null>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/summary?user_id=${encodeURIComponent(userId)}`);
}
