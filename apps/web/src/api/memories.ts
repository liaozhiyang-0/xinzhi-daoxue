import type { MemoryRead } from "../api-types.js";
import { apiRequest, jsonBody } from "./client.js";

export function listMemories(userId: string): Promise<MemoryRead[]> {
  return apiRequest<MemoryRead[]>(`/api/v1/memories?user_id=${encodeURIComponent(userId)}`);
}

export function createMemory(userId: string, content: string, sourceSessionId?: string): Promise<MemoryRead> {
  return apiRequest<MemoryRead>("/api/v1/memories", {
    method: "POST",
    body: jsonBody({ user_id: userId, content, source_session_id: sourceSessionId || null }),
  });
}

export function updateMemory(memoryId: string, userId: string, content: string): Promise<MemoryRead> {
  return apiRequest<MemoryRead>(`/api/v1/memories/${encodeURIComponent(memoryId)}`, {
    method: "PATCH",
    body: jsonBody({ user_id: userId, content }),
  });
}

export function deleteMemory(memoryId: string, userId: string): Promise<unknown> {
  return apiRequest(`/api/v1/memories/${encodeURIComponent(memoryId)}?user_id=${encodeURIComponent(userId)}`, { method: "DELETE" });
}
