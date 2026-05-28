/**
 * Admin user-management hooks (feature 009).  Thin React-Query wrappers over
 * the `/api/v1/users` endpoints; the surface is admin-only server-side
 * (`require_admin`), so a non-admin who reaches these calls gets a 403.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type AdminUser = components["schemas"]["UserOut"];
export type UserCreateBody = components["schemas"]["UserCreate"];
export type CreatedUser = components["schemas"]["CreatedUser"];

export const ADMIN_USERS_QUERY_KEY = ["admin", "users"] as const;

export async function listUsers(): Promise<AdminUser[]> {
  const { data, error } = await client.GET("/api/v1/users");
  if (error || !data) {
    throw new Error("Failed to load users");
  }
  return data.items;
}

export function useUsers() {
  return useQuery({
    queryKey: ADMIN_USERS_QUERY_KEY,
    queryFn: listUsers,
  });
}

/** Field a {@link CreateUserError} should attach to (else the form banner). */
export type CreateUserField = "email" | "password" | "form";

/** Typed error so the dialog can surface 409 (email) vs 422 distinctly. */
export class CreateUserError extends Error {
  readonly field: CreateUserField;
  constructor(field: CreateUserField, message: string) {
    super(message);
    this.name = "CreateUserError";
    this.field = field;
  }
}

/**
 * Create a user (`POST /api/v1/users`).  A duplicate email is a **409**
 * (mapped to the email field); a short/invalid password or malformed email is
 * a **422**.  On success the cache is invalidated so the list refreshes, and
 * the response (which may carry a one-time `temporary_password`) is returned to
 * the caller to display once.
 */
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: UserCreateBody): Promise<CreatedUser> => {
      const { data, error, response } = await client.POST("/api/v1/users", {
        body,
      });
      if (response.status === 409) {
        throw new CreateUserError(
          "email",
          "A user with that email already exists.",
        );
      }
      if (response.status === 422) {
        throw new CreateUserError(
          "password",
          "Check the email and password — the password must be at least 12 characters.",
        );
      }
      if (error || !data) {
        throw new CreateUserError(
          "form",
          "Could not create the user. Please try again.",
        );
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
    },
  });
}
