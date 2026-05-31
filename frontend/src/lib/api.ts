/**
 * Type-safe API client using openapi-fetch and generated types.
 *
 * The types in `@/api/v1.d.ts` are auto-generated from the FastAPI
 * OpenAPI spec by `scripts/generate_openapi_client.py`.
 *
 * Cookies are sent on every request (`credentials: "include"`) so the
 * server-issued `mm_session` cookie is attached.  A response middleware
 * watches for 401s on non-`/auth/*` endpoints and invokes the
 * runtime-injected `onUnauthenticated` callback (set in `main.tsx`) so
 * the cache is cleared and the user lands on `/login` (FR-008).
 *
 * A request middleware implements the CSRF double-submit (ADR-0019): it
 * echoes the non-HttpOnly `mm_csrf` cookie in the `X-CSRF-Token` header on
 * every unsafe (state-changing) request.
 */

import createClient, { type Middleware } from "openapi-fetch";
import type { QueryClient } from "@tanstack/react-query";
import type { paths } from "@/api/v1";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  credentials: "include",
});

interface ApiContext {
  queryClient: QueryClient;
  onUnauthenticated: () => void;
}

let apiContext: ApiContext | null = null;

export function setApiContext(ctx: ApiContext): void {
  apiContext = ctx;
}

const CSRF_COOKIE_NAME = "mm_csrf";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export const csrfMiddleware: Middleware = {
  async onRequest({ request }) {
    if (UNSAFE_METHODS.has(request.method.toUpperCase())) {
      const token = readCookie(CSRF_COOKIE_NAME);
      if (token) {
        request.headers.set("X-CSRF-Token", token);
      }
    }
    return request;
  },
};

const authMiddleware: Middleware = {
  async onResponse({ response, request }) {
    if (response.status === 401) {
      // Use a placeholder base so relative URLs parse cleanly.
      const path = new URL(request.url, "http://placeholder").pathname;
      // /auth/* are the login/logout endpoints themselves; /me is the
      // logged-in probe used by useCurrentUser() — a 401 there means
      // "logged out" and is the caller's signal, not a session-expiry
      // event that should boot the user to /login.
      if (!path.startsWith("/auth/") && path !== "/me") {
        apiContext?.queryClient.clear();
        apiContext?.onUnauthenticated();
      }
    }
    return response;
  },
};

client.use(csrfMiddleware);
client.use(authMiddleware);

export interface HealthzResponse {
  status: string;
}

/**
 * Fetch the /healthz endpoint using the generated type-safe client.
 */
export async function fetchHealthz(): Promise<HealthzResponse> {
  const { data, error } = await client.GET("/healthz");
  if (error) {
    throw new Error("Health check failed");
  }
  return data as unknown as HealthzResponse;
}
