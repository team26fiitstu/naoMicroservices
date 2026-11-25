// Base URL of the backend. Empty = same origin, nginx (or the Vite dev proxy) routes requests to the services.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// Failed backend request, message has status and server detail
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    const fields = (body ?? {}) as Record<string, unknown>;
    const details = [fields.detail, fields.error, fields.message].filter((d) => typeof d === "string" && d);
    super(`HTTP ${status}${details.length ? `, ${details.join(", ")}` : ""}`);
    this.status = status;
    this.body = body;
  }
}

type RequestOptions = { method?: string; json?: unknown; body?: BodyInit };

// Backend request, json is sent as JSON body, returns parsed JSON response
export async function api<T = unknown>(path: string, { method, json, body }: RequestOptions = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: json === undefined ? undefined : { "Content-Type": "application/json" },
    body: json === undefined ? body : JSON.stringify(json),
  });
  const data = await res.json().catch(() => undefined);
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}
