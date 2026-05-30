/**
 * `GET /api/v1/adherence/medications/{id}` query hook (Phase 9).
 *
 * One payload feeds both the calendar and the trend (research D7). Cache key
 * includes the window + timezone so paging months / switching window refetches.
 */

import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { DateWindow, MedicationAdherence } from "@/lib/adherence";

export const adherenceKey = (
  id: string,
  window: DateWindow,
  timezone?: string,
) => ["adherence", id, window.from, window.to, timezone ?? null] as const;

export function useMedicationAdherence(
  medicationId: string,
  window: DateWindow,
  timezone?: string,
) {
  return useQuery<MedicationAdherence>({
    queryKey: adherenceKey(medicationId, window, timezone),
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/adherence/medications/{medication_id}",
        {
          params: {
            path: { medication_id: medicationId },
            query: { from: window.from, to: window.to, timezone },
          },
        },
      );
      if (error || !data) {
        throw new Error("Failed to load adherence");
      }
      return data;
    },
  });
}
