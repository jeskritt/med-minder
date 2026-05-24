/**
 * In-app reminders hook (Phase 7, FR-008): the user's open reminders.
 */

import { useQuery } from "@tanstack/react-query";
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
