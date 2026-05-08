/**
 * `GET /api/schedules/today` query hook.
 *
 * The cache key includes the timezone passed by the caller (or
 * `undefined` to use the server-side default from `users.timezone`).
 * `useTakeDose` and `useUntakeDose` snapshot and write through this
 * exact key, so it must round-trip cleanly.
 */

import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type TodayItem = components["schemas"]["TodayItem"];
export type TodayResponse = components["schemas"]["TodayResponse"];

export const todayQueryKey = (timezone?: string) =>
  ["today", timezone ?? null] as const;

export function useToday(timezone?: string) {
  return useQuery<TodayResponse>({
    queryKey: todayQueryKey(timezone),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/schedules/today", {
        params: { query: timezone ? { timezone } : {} },
      });
      if (error || !data) {
        throw new Error("Failed to load today");
      }
      return data;
    },
    staleTime: 10_000,
  });
}
