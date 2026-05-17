/**
 * `GET /api/v1/medications/{medication_id}` query hook.
 *
 * Cache key `["medication", id]`; refetches on window focus so the
 * timer state re-syncs to the server when the user returns to the tab.
 */

import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type MedicationDetail = components["schemas"]["MedicationDetailOut"];

export const medicationDetailKey = (id: string) => ["medication", id] as const;

export function useMedicationDetail(id: string) {
  return useQuery<MedicationDetail>({
    queryKey: medicationDetailKey(id),
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/medications/{medication_id}",
        { params: { path: { medication_id: id } } },
      );
      if (error || !data) {
        throw new Error("Failed to load medication");
      }
      return data;
    },
    refetchOnWindowFocus: true,
  });
}
