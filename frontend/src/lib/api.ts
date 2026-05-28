/**
 * Typed fetch client for RPA Intelligence API
 * Handles authentication, error responses, and JSON serialization
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: string
  ) {
    super(`API Error ${status}: ${statusText}`)
    this.name = "ApiError"
  }
}

/**
 * Generic typed fetch wrapper with automatic Bearer token injection
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null

  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> ?? {}),
  }

  // Only add Content-Type for non-FormData requests
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json"
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })

  if (!res.ok) {
    const text = await res.text()
    throw new ApiError(res.status, res.statusText, text)
  }

  // Handle empty responses (204 No Content)
  const contentType = res.headers.get("content-type")
  if (!contentType || res.status === 204) {
    return undefined as T
  }

  if (contentType.includes("application/json")) {
    return res.json()
  }

  // For non-JSON responses (like file downloads), return the response itself
  return res as unknown as T
}

/**
 * Helper for GET requests
 */
export function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" })
}

/**
 * Helper for POST requests with JSON body
 */
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * Helper for POST requests with FormData (file uploads)
 */
export function apiPostFormData<T>(path: string, formData: FormData): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: formData,
  })
}

/**
 * Helper for PATCH requests with JSON body
 */
export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

/**
 * Helper for PUT requests with JSON body
 */
export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PUT",
    body: JSON.stringify(body),
  })
}

/**
 * Helper for DELETE requests
 */
export function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "DELETE" })
}

/**
 * Store authentication token in localStorage
 */
export function setAuthToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("token", token)
  }
}

/**
 * Remove authentication token from localStorage
 */
export function clearAuthToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token")
  }
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false
  return localStorage.getItem("token") !== null
}
