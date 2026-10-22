import type { AuthUser } from "./auth";
import { getValidToken } from "./auth";
import type {
  EmailDraft,
  EmailHint,
  JobRecord,
  JobsListResponse,
  ProvidersResponse,
  SearchHistoryRow,
  ServerStatus,
  TaskRecord,
} from "./types";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  payload: unknown;
  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// Automatically attaches Bearer token when present.
// On 401, attempts one silent token refresh then retries once.
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown; _retry?: boolean },
): Promise<T> {
  const headers = new Headers(init?.headers);
  let body: BodyInit | null | undefined = init?.body ?? null;

  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }

  // Attach auth token when available
  const token = await getValidToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(path, { ...init, headers, body });
  const text = await res.text();
  let payload: unknown = undefined;
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = text; }
  }

  if (!res.ok) {
    // On 401 — attempt one silent refresh and retry
    if (res.status === 401 && !init?._retry) {
      const fresh = await getValidToken();
      if (fresh) {
        return request<T>(path, { ...init, _retry: true });
      }
      // Refresh failed — redirect to login
      window.location.href = "/login";
      throw new ApiError(401, "Session expired. Please log in.", payload);
    }
    const message =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof (payload as { detail: unknown }).detail === "string"
        ? (payload as { detail: string }).detail
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, message, payload);
  }
  return payload as T;
}

// ---------------------------------------------------------------------------
// Auth endpoints (no Bearer token needed — these ARE the auth layer)
// ---------------------------------------------------------------------------

async function authRequest<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers = new Headers(init?.headers);
  let body: BodyInit | null | undefined = init?.body ?? null;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const res = await fetch(path, { ...init, headers, body });
  const text = await res.text();
  let payload: unknown = undefined;
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = text; }
  }
  if (!res.ok) {
    const message =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof (payload as { detail: unknown }).detail === "string"
        ? (payload as { detail: string }).detail
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, message, payload);
  }
  return payload as T;
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────
  auth: {
    register: (email: string, password: string) =>
      authRequest<{ user_id: string; message: string }>("/api/auth/register", {
        method: "POST",
        json: { email, password },
      }),
    login: (email: string, password: string) =>
      authRequest<{ access_token: string; refresh_token: string; token_type: string }>(
        "/api/auth/login",
        { method: "POST", json: { email, password } },
      ),
    logout: (refreshToken: string) =>
      authRequest<{ message: string }>("/api/auth/logout", {
        method: "POST",
        json: { refresh_token: refreshToken },
      }),
    me: (accessToken: string) =>
      fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).then(r => r.json()) as Promise<AuthUser>,
    verifyEmail: (token: string) =>
      authRequest<{ message: string }>(`/api/auth/verify-email?token=${encodeURIComponent(token)}`),
    resendVerification: (email: string) =>
      authRequest<{ message: string }>("/api/auth/resend-verification", {
        method: "POST",
        json: { email },
      }),
    requestPasswordReset: (email: string) =>
      authRequest<{ message: string }>("/api/auth/password-reset/request", {
        method: "POST",
        json: { email },
      }),
    confirmPasswordReset: (token: string, newPassword: string) =>
      authRequest<{ message: string }>("/api/auth/password-reset/confirm", {
        method: "POST",
        json: { token, new_password: newPassword },
      }),
    refresh: (refreshToken: string) =>
      authRequest<{ access_token: string }>("/api/auth/refresh", {
        method: "POST",
        json: { refresh_token: refreshToken },
      }),
  },

  // ── Platform ─────────────────────────────────────────────────────────────
  status: () => request<ServerStatus>("/api/status"),
  providers: () => request<ProvidersResponse>("/api/providers"),
  jobs: () => request<JobsListResponse>("/api/jobs"),
  job: (jobId: string) => request<JobRecord>(`/api/jobs/${jobId}`),
  deleteJob: (jobId: string) =>
    request<{ deleted: string }>(`/api/jobs/${jobId}`, { method: "DELETE" }),
  deleteAllJobs: () =>
    request<{ deleted_count: number; workspace_total_jobs: number }>("/api/jobs", { method: "DELETE" }),
  searches: () =>
    request<{ workspace: string; searches: SearchHistoryRow[] }>("/api/searches"),
  deleteSearch: (id: number) =>
    request<{ deleted: number }>(`/api/searches/${id}`, { method: "DELETE" }),
  deleteAllSearches: () =>
    request<{ deleted_count: number }>("/api/searches", { method: "DELETE" }),
  task: (taskId: string) => request<TaskRecord>(`/api/tasks/${taskId}`),
  tasksList: (limit = 25) =>
    request<{ tasks: TaskRecord[] }>(`/api/tasks?limit=${limit}`),
  cancelTask: (taskId: string) =>
    request<{ cancelled: string }>(`/api/tasks/${taskId}/cancel`, { method: "POST" }),
  search: (body: {
    titles: string[];
    skills?: string[];
    location?: string;
    remote?: boolean;
    results_wanted?: number;
    sites?: string[];
    score?: boolean;
    provider?: string;
    model?: string;
    linkedin_descriptions?: boolean;
    force?: boolean;
    experience_level?: string;
    job_type?: string;
  }) => request<TaskRecord>("/api/search", { method: "POST", json: body }),
  run: (body: {
    job_ids: string[];
    provider?: string;
    model?: string;
    no_pdf?: boolean;
    force?: boolean;
  }) => request<TaskRecord>("/api/run", { method: "POST", json: body }),
  tailor: (jobId: string, body: { provider?: string; model?: string; no_pdf?: boolean } = {}) =>
    request<TaskRecord>(`/api/jobs/${jobId}/tailor`, { method: "POST", json: body }),
  freeform: (body: {
    description: string;
    title?: string;
    company?: string;
    location?: string;
    skills?: string[];
    provider?: string;
    model?: string;
    no_pdf?: boolean;
  }) => request<TaskRecord>("/api/freeform", { method: "POST", json: body }),
  email: (jobId: string, body: {
    recipient: string;
    additional_info?: string;
    provider?: string;
    model?: string;
  }) => request<TaskRecord>(`/api/jobs/${jobId}/email`, { method: "POST", json: body }),
  emailHint: (jobId: string) => request<EmailHint>(`/api/jobs/${jobId}/email-hint`),
  artifactUrl: (jobId: string, name: string) =>
    `/api/jobs/${jobId}/artifacts/${encodeURIComponent(name)}`,
  artifactText: async (jobId: string, name: string): Promise<string> => {
    const token = await getValidToken();
    const res = await fetch(`/api/jobs/${jobId}/artifacts/${encodeURIComponent(name)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`, null);
    return res.text();
  },
  saveArtifact: (jobId: string, name: string, content: string) =>
    request<{ name: string; bytes: number; mtime: number; saved: string }>(
      `/api/jobs/${jobId}/artifacts/${encodeURIComponent(name)}`,
      { method: "PUT", json: { content } },
    ),
  compileArtifact: (jobId: string, name: string) =>
    request<{ name: string; size: number; mtime: number; backend: string }>(
      `/api/jobs/${jobId}/artifacts/${encodeURIComponent(name)}/compile`,
      { method: "POST" },
    ),
};

export type { EmailDraft, EmailHint };
