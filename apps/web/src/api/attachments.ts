import type { FileRead } from "../api-types.js";
import { apiRequest } from "./client.js";

export async function uploadAttachment(file: File): Promise<FileRead> {
  const body = new FormData();
  body.append("upload", file);
  body.append("purpose", "unified_task_material");
  return apiRequest<FileRead>("/api/v1/files", { method: "POST", body });
}
