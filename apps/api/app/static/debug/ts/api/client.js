export class ApiError extends Error {
    status;
    details;
    constructor(message, status, details = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.details = details;
    }
}
function responseMessage(payload, fallback) {
    if (typeof payload === "object" && payload !== null && "error" in payload) {
        const error = payload.error;
        if (typeof error?.message === "string")
            return error.message;
    }
    if (typeof payload === "object" && payload !== null && "detail" in payload) {
        const detail = payload.detail;
        if (typeof detail === "string")
            return detail;
    }
    return fallback;
}
export async function apiRequest(path, init = {}) {
    const headers = new Headers(init.headers);
    if (init.body && !(init.body instanceof FormData)) {
        headers.set("Content-Type", "application/json");
    }
    const response = await fetch(path, { ...init, headers });
    const text = await response.text();
    let payload = null;
    if (text) {
        try {
            payload = JSON.parse(text);
        }
        catch {
            payload = text;
        }
    }
    if (!response.ok) {
        throw new ApiError(responseMessage(payload, `请求失败（${response.status}）`), response.status, payload);
    }
    return payload;
}
export function jsonBody(value) {
    return JSON.stringify(value);
}
