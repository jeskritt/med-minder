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

/**
 * Update the current user's display name (`PATCH /me`).  Invalidates the
 * `["me"]` query on success so the nav bar reflects the new name without a
 * reload (FR-008).
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string }): Promise<Me> => {
      const { data, error, response } = await client.PATCH("/me", {
        body: input,
      });
      if (error || !data) {
        throw new Error(
          response.status === 422
            ? "That name isn't valid."
            : "Could not save your name. Please try again.",
        );
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: [...meQueryKey] });
    },
  });
}

/** Which field a {@link ChangePasswordError} should attach to. */
export type ChangePasswordField = "current_password" | "new_password" | "form";

/** Typed error so the dialog can surface 403 vs 422 on the right field. */
export class ChangePasswordError extends Error {
  readonly field: ChangePasswordField;
  constructor(field: ChangePasswordField, message: string) {
    super(message);
    this.name = "ChangePasswordError";
    this.field = field;
  }
}

/**
 * Change the current user's password (`POST /me/password`).  The server
 * verifies the current password, revokes every other session, and re-issues
 * this device's cookie — so the user stays signed in here (FR-005).  A wrong
 * current password is a **403** (mapped to the current-password field); a
 * too-short new password is a **422** (FR-003).
 */
export function useChangePassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      current_password: string;
      new_password: string;
    }): Promise<void> => {
      const { error, response } = await client.POST("/me/password", {
        body: input,
      });
      if (response.status === 403) {
        throw new ChangePasswordError(
          "current_password",
          "Current password is incorrect.",
        );
      }
      if (response.status === 422) {
        throw new ChangePasswordError(
          "new_password",
          "Password must be at least 12 characters.",
        );
      }
      if (error || response.status !== 204) {
        throw new ChangePasswordError(
          "form",
          "Could not change your password. Please try again.",
        );
      }
    },
    onSuccess: async () => {
      // The session cookie was rotated server-side; refetch /me to be safe.
      await queryClient.invalidateQueries({ queryKey: [...meQueryKey] });
    },
  });
}
