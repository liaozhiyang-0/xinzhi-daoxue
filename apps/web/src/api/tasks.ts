import type {
  EventRead,
  TaskRead,
  TaskRuntimeControlProjectionRead,
} from "../api-types.js";
import type { StudentTaskPayload } from "../workspace-contracts.js";
import { apiRequest, jsonBody } from "./client.js";

export function createTask(payload: StudentTaskPayload): Promise<TaskRead> {
  return apiRequest<TaskRead>("/api/v1/tasks", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function getTask(taskId: string): Promise<TaskRead> {
  return apiRequest<TaskRead>(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
}

export function cancelTask(taskId: string): Promise<TaskRead> {
  return apiRequest<TaskRead>(`/api/v1/tasks/${encodeURIComponent(taskId)}/cancel`, {
    method: "POST",
    body: jsonBody({}),
  });
}

export function retryTask(taskId: string): Promise<TaskRead> {
  return apiRequest<TaskRead>(`/api/v1/tasks/${encodeURIComponent(taskId)}/retry`, {
    method: "POST",
  });
}

export function pauseTask(taskId: string, runtimeRunId?: string): Promise<TaskRead> {
  const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
  return apiRequest<TaskRead>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/pause${query}`,
    { method: "POST" },
  );
}

export function resumeTask(taskId: string, runtimeRunId?: string): Promise<TaskRead> {
  const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
  return apiRequest<TaskRead>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/resume${query}`,
    { method: "POST" },
  );
}

export function approveTask(taskId: string, runtimeRunId?: string): Promise<TaskRead> {
  const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
  return apiRequest<TaskRead>(`/api/v1/tasks/${encodeURIComponent(taskId)}/approve${query}`, { method: "POST" });
}

export function submitRuntimeInput(taskId: string, input: string, runtimeRunId?: string): Promise<TaskRead> {
  const query = runtimeRunId ? `?runtime_run_id=${encodeURIComponent(runtimeRunId)}` : "";
  return apiRequest<TaskRead>(`/api/v1/tasks/${encodeURIComponent(taskId)}/input${query}`, {
    method: "POST",
    body: jsonBody({ input }),
  });
}

export function getTaskRuntimeControls(
  taskId: string,
): Promise<TaskRuntimeControlProjectionRead> {
  return apiRequest<TaskRuntimeControlProjectionRead>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/runtime-controls`,
  );
}

export function listTaskEvents(taskId: string, after = 0): Promise<EventRead[]> {
  return apiRequest<EventRead[]>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/events?after=${after}`,
  );
}
