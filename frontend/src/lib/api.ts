import type { AuthSession } from "../types";

const authBase = (import.meta.env?.VITE_AUTH_API_BASE || "").replace(/\/$/, "");
export const agentBase = (import.meta.env?.VITE_AGENT_API_BASE || "").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function responseError(response: Response): Promise<ApiError> {
  let message = "Не удалось выполнить запрос. Попробуйте ещё раз.";
  if (response.status === 401) message = "Сессия завершилась. Войдите ещё раз.";
  if (response.status === 429)
    message = "Слишком много запросов. Попробуйте позже.";
  if (response.status >= 500)
    message = "Сервис временно недоступен. Попробуйте чуть позже.";
  try {
    const payload: unknown = await response.json();
    if (payload && typeof payload === "object" && "detail" in payload) {
      if (typeof payload.detail === "string" && response.status < 500) {
        message = payload.detail;
      } else if (Array.isArray(payload.detail) && response.status === 422) {
        message = "Проверьте почту и заполненные поля.";
      }
    }
  } catch {
    // A reverse proxy may return an HTML error page.
  }
  return new ApiError(message, response.status);
}

async function authRequest<T>(
  path: string,
  method = "GET",
  body?: object,
  csrf?: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${authBase}/api/v1/auth/${path}`, {
    method,
    credentials: "include",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-Requested-With": "PartnerAgent" } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: signal || AbortSignal.timeout(15000),
  });
  if (!response.ok) throw await responseError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const authApi = {
  me: (signal?: AbortSignal) =>
    authRequest<AuthSession>("me", "GET", undefined, undefined, signal),
  login: (email: string, password: string) =>
    authRequest<AuthSession>("login", "POST", { email, password }),
  register: (name: string, email: string, password: string) =>
    authRequest<AuthSession>("register", "POST", { name, email, password }),
  logout: (csrf: string) =>
    authRequest<void>("logout", "POST", undefined, csrf),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof DOMException && error.name === "TimeoutError")
    return "Сервис отвечает слишком долго. Попробуйте ещё раз.";
  return "Не удалось связаться с сервисом. Проверьте подключение и повторите запрос.";
}

export function safeSourceUrl(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

async function chatRequest<T>(path: string, method = "GET", csrf?: string, body?: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${agentBase}/api/v1${path}`, {
    method,
    credentials: "include",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-Requested-With": "PartnerAgent" } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: signal || AbortSignal.timeout(15000),
  });
  if (!response.ok) throw await responseError(response);
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

export const chatApi = {
  list: async (signal?: AbortSignal): Promise<import("../types").Conversation[]> => {
    const result: import("../types").Conversation[] = [];
    for (let offset = 0; ; offset += 100) {
      const page = await chatRequest<Omit<import("../types").Conversation, "messages">[]>(`/conversations?limit=100&offset=${offset}`, "GET", undefined, undefined, signal);
      result.push(...page.map((chat) => ({ ...chat, messages: [] })));
      if (page.length < 100) return result;
    }
  },
  get: (id: string, signal?: AbortSignal) => chatRequest<import("../types").Conversation>(`/conversations/${id}`, "GET", undefined, undefined, signal),
  create: (title: string, csrf: string, signal?: AbortSignal) => chatRequest<import("../types").Conversation>("/conversations", "POST", csrf, { title }, signal),
  remove: (id: string, csrf: string) => chatRequest<void>(`/conversations/${id}`, "DELETE", csrf),
  cancel: (id: string, requestId: string, csrf: string) => chatRequest<void>(`/conversations/${id}/requests/${requestId}/cancel`, "POST", csrf),
};
