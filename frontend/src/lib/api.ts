/**
 * Type-safe API client using openapi-fetch and generated types.
 *
 * The types in `@/api/v1.d.ts` are auto-generated from the FastAPI
 * OpenAPI spec by `scripts/generate_openapi_client.py`.
 */

import createClient from "openapi-fetch";
import type { paths } from "@/api/v1";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

const client = createClient<paths>({
  baseUrl: API_BASE_URL,
});

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
