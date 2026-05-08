/**
 * `POST /api/doses` with optimistic update of the Today query cache.
 *
 * Lifecycle (per FR-008 + research §"Optimistic UI updates"):
 *
 * - `onMutate` cancels in-flight refetches, snapshots the cached
 *   `TodayResponse`, and writes an optimistic synthetic dose into the
 *   matching slot.
 * - `onError` restores the snapshot.
 * - `onSettled` invalidates the Today key so the next read reconciles
 *   with the server.
 *
 * The toast emission is delegated to the caller (the `onError`
 * callback) so this hook stays pure and testable without a toast
 * provider.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import { todayQueryKey, type TodayResponse } from "@/hooks/useToday";

export interface TakeDoseInput {
  medicationId: string;
  scheduleId: string;
  timezone?: string;
}

interface TakeContext {
  previous: TodayResponse | undefined;
  key: ReturnType<typeof todayQueryKey>;
}

export function useTakeDose() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, TakeDoseInput, TakeContext>({
    mutationFn: async (input) => {
      const { error } = await client.POST("/api/doses", {
        body: {
          medication_id: input.medicationId,
          schedule_id: input.scheduleId,
          taken_at: new Date().toISOString(),
        },
      });
      if (error) {
        throw new Error("Failed to mark dose as taken");
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
              ? {
                  ...item,
                  dose: {
                    id: `optimistic-${input.scheduleId}-${input.medicationId}`,
                    taken_at: new Date().toISOString(),
                  },
                }
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
