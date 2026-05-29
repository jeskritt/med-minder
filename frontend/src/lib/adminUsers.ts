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
export type UserUpdateBody = components["schemas"]["UserUpdate"];
export type CreatedUser = components["schemas"]["CreatedUser"];
export type PasswordSetBody = components["schemas"]["PasswordSet"];
export type PasswordResetOut = components["schemas"]["PasswordResetOut"];
export type AuditEntry = components["schemas"]["AuditEntryOut"];

export const ADMIN_USERS_QUERY_KEY = ["admin", "users"] as const;
export const ADMIN_AUDIT_QUERY_KEY = ["admin", "audit"] as const;

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

/**
 * Edit a user's name/email/role (`PATCH /api/v1/users/{id}`).  A duplicate
 * email is a **409** (email field); editing your own row is a **403** (the UI
 * disables that, so it's a backstop); other failures map to the form banner.
 */
export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      userId: string;
      body: UserUpdateBody;
    }): Promise<AdminUser> => {
      const { data, error, response } = await client.PATCH(
        "/api/v1/users/{user_id}",
        { params: { path: { user_id: input.userId } }, body: input.body },
      );
      if (response.status === 409) {
        throw new CreateUserError(
          "email",
          "A user with that email already exists.",
        );
      }
      if (error || !data) {
        throw new CreateUserError(
          "form",
          "Could not save the changes. Please try again.",
        );
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
    },
  });
}

/**
 * Reset a user's password (`POST /api/v1/users/{id}/password`).  Typed or
 * generated; a generated one comes back in `temporary_password` to show once.
 * Resetting your own password here is a **403** (use the profile editor).
 */
export function useResetPassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      userId: string;
      body: PasswordSetBody;
    }): Promise<PasswordResetOut> => {
      const { data, error, response } = await client.POST(
        "/api/v1/users/{user_id}/password",
        { params: { path: { user_id: input.userId } }, body: input.body },
      );
      if (response.status === 422) {
        throw new CreateUserError(
          "password",
          "Password must be at least 12 characters.",
        );
      }
      if (error || !data) {
        throw new CreateUserError(
          "form",
          "Could not reset the password. Please try again.",
        );
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
    },
  });
}

/**
 * Deactivate (soft-delete) a user (`DELETE /api/v1/users/{id}`).  The list is
 * invalidated so the row disappears.  The self and last-admin guards are
 * server-side (the UI also disables the self-row action).
 */
export function useDeactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string): Promise<void> => {
      const { error, response } = await client.DELETE(
        "/api/v1/users/{user_id}",
        { params: { path: { user_id: userId } } },
      );
      if (error || response.status !== 204) {
        throw new Error("Could not deactivate the user. Please try again.");
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY });
    },
  });
}

export async function listAuditLog(): Promise<AuditEntry[]> {
  const { data, error } = await client.GET("/api/v1/users/audit-log");
  if (error || !data) {
    throw new Error("Failed to load the audit log");
  }
  return data.items;
}

/** Read-only admin audit trail, newest first (`GET /api/v1/users/audit-log`). */
export function useAuditLog() {
  return useQuery({
    queryKey: ADMIN_AUDIT_QUERY_KEY,
    queryFn: listAuditLog,
  });
}
