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
import type { components } from "@/api/v1";

type MinIntervalViolation = components["schemas"]["MinIntervalViolation"];
type WindowFullViolation = components["schemas"]["WindowFullViolation"];

export class MinIntervalError extends Error {
  readonly body: MinIntervalViolation;

  constructor(body: MinIntervalViolation) {
    super("min_interval_not_elapsed");
    this.name = "MinIntervalError";
    this.body = body;
  }
}

export class WindowFullError extends Error {
  readonly body: WindowFullViolation;

  constructor(body: WindowFullViolation) {
    super("window_full");
    this.name = "WindowFullError";
    this.body = body;
  }
}

export interface TakeDoseInput {
  medicationId: string;
  scheduleId?: string;
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
      const { error, response } = await client.POST("/api/doses", {
        body: {
          medication_id: input.medicationId,
          schedule_id: input.scheduleId ?? null,
          taken_at: new Date().toISOString(),
        },
      });
      if (response.status === 409 && error) {
        const body = error as MinIntervalViolation | WindowFullViolation;
        if (body.code === "window_full") {
          throw new WindowFullError(body);
        }
        throw new MinIntervalError(body);
      }
      if (error) {
        throw new Error("Failed to mark dose as taken");
      }
    },
    onMutate: async (input) => {
      const key = todayQueryKey(input.timezone);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<TodayResponse>(key);
      if (previous && input.scheduleId !== undefined) {
        const scheduleId = input.scheduleId;
        const next: TodayResponse = {
          ...previous,
          items: previous.items.map((item) =>
            item.schedule_id === scheduleId &&
            item.medication_id === input.medicationId
              ? {
                  ...item,
                  dose: {
                    id: `optimistic-${scheduleId}-${input.medicationId}`,
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
    onSettled: (_data, _err, input, context) => {
      if (context) {
        void queryClient.invalidateQueries({ queryKey: context.key });
      }
      // The dose also changes timer state shown on the medications list
      // and the single-medication detail page. Without these the
      // count/CTA on those views stays stale after marking from there
      // (no schedule context → no optimistic today patch either).
      void queryClient.invalidateQueries({ queryKey: ["medications"] });
      void queryClient.invalidateQueries({
        queryKey: ["medication", input.medicationId],
      });
    },
  });
}
