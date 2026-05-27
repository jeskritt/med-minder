/**
 * In-app reminders hook (Phase 7, FR-008): the user's open reminders.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type ReminderOut = components["schemas"]["ReminderOut"];

export const REMINDERS_QUERY_KEY = ["reminders"] as const;

export async function listReminders(): Promise<ReminderOut[]> {
  const { data, error } = await client.GET("/api/v1/reminders");
  if (error || !data) {
    throw new Error("Failed to load reminders");
  }
  return data.items;
}

export function useReminders() {
  return useQuery({
    queryKey: REMINDERS_QUERY_KEY,
    queryFn: listReminders,
  });
}

/** Snooze a reminder one hour (US2). Refetches the list on success. */
export function useSnoozeReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (reminderId: string): Promise<void> => {
      const { error } = await client.POST(
        "/api/v1/reminders/{reminder_id}/snooze",
        { params: { path: { reminder_id: reminderId } } },
      );
      if (error) {
        throw new Error("Could not snooze the reminder.");
      }
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: REMINDERS_QUERY_KEY }),
  });
}

/** Dismiss (resolve) a reminder (US2). Refetches the list on success. */
export function useDismissReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (reminderId: string): Promise<void> => {
      const { error } = await client.POST(
        "/api/v1/reminders/{reminder_id}/dismiss",
        { params: { path: { reminder_id: reminderId } } },
      );
      if (error) {
        throw new Error("Could not dismiss the reminder.");
      }
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: REMINDERS_QUERY_KEY }),
  });
}
