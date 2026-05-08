/**
 * `POST /api/doses/{id}/void` with optimistic clearing of the slot.
 *
 * Mirrors `useTakeDose`: snapshot the today cache, optimistically clear
 * `dose` for the matching slot, restore on error, invalidate on settle.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import { todayQueryKey, type TodayResponse } from "@/hooks/useToday";

export interface UntakeDoseInput {
  doseId: string;
  scheduleId: string;
  medicationId: string;
  timezone?: string;
}

interface UntakeContext {
  previous: TodayResponse | undefined;
  key: ReturnType<typeof todayQueryKey>;
}

export function useUntakeDose() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, UntakeDoseInput, UntakeContext>({
    mutationFn: async (input) => {
      const { error } = await client.POST("/api/doses/{dose_id}/void", {
        params: { path: { dose_id: input.doseId } },
      });
      if (error) {
        throw new Error("Failed to un-take dose");
      }
    },
    onMutate: async (input) => {
      const key = todayQueryKey(input.timezone);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<TodayResponse>(key);
      if (previous) {
        const next: TodayResponse = {
          ...previous,
          items: previous.items.map((item) =>
            item.schedule_id === input.scheduleId &&
            item.medication_id === input.medicationId
              ? { ...item, dose: null }
              : item,
          ),
        };
        queryClient.setQueryData(key, next);
      }
      return { previous, key };
    },
    onError: (_err, _input, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.key, context.previous);
      }
    },
    onSettled: (_data, _err, _input, context) => {
      if (context) {
        void queryClient.invalidateQueries({ queryKey: context.key });
      }
    },
  });
}
