import { apiRequest } from "./client.js";
export async function uploadAttachment(file) {
    const body = new FormData();
    body.append("upload", file);
    body.append("purpose", "unified_task_material");
    return apiRequest("/api/v1/files", { method: "POST", body });
}
