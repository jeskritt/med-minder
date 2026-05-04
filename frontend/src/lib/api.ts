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

const authMiddleware: Middleware = {
  async onResponse({ response, request }) {
    if (response.status === 401) {
      // Use a placeholder base so relative URLs parse cleanly.
      const path = new URL(request.url, "http://placeholder").pathname;
      if (!path.startsWith("/auth/")) {
        apiContext?.queryClient.clear();
        apiContext?.onUnauthenticated();
      }
    }
    return response;
  },
};

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
