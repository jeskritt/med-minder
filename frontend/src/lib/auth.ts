/**
 * Auth React-Query hooks: `useCurrentUser`, `useLogout`.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type Me = components["schemas"]["Me"];

export const meQueryKey = ["me"] as const;

/**
 * Cached `GET /me`.  Returns `null` when the server replies 401 so
 * components can branch on "logged out" without throwing.
 */
export function useCurrentUser() {
  return useQuery<Me | null>({
    queryKey: [...meQueryKey],
    queryFn: async () => {
      const { data, response } = await client.GET("/me");
      if (response.status === 401) {
        return null;
      }
      if (!data) {
        throw new Error("Failed to fetch current user");
      }
      return data;
    },
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * Logout mutation.  Clears every cached query on settlement so a fresh
 * login as a different user starts with an empty cache.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error } = await client.POST("/auth/logout");
      if (error) {
        throw new Error("Logout failed");
      }
    },
    onSettled: async () => {
      queryClient.clear();
    },
  });
}
