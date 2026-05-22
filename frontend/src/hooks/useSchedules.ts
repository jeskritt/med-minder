/**
 * Shared-schedule CRUD hooks (UX-enhancements).
 *
 * Schedules became user-level resources: one Schedule row may back
 * multiple medications via `ScheduleMedication`. The medication form
 * picks from the user's existing schedules and may inline-create new
 * ones via this hook set. The legacy ``GET /api/schedules/today``
 * surface is untouched; this targets ``/api/v1/schedules``.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type ScheduleOut = components["schemas"]["ScheduleCrudOut"];
export type ScheduleMedRef = components["schemas"]["ScheduleMedRef"];
type ScheduleWriteBody = components["schemas"]["ScheduleWriteBody"];

export const SCHEDULES_QUERY_KEY = ["schedules"] as const;

export async function listSchedules(): Promise<ScheduleOut[]> {
  const { data, error } = await client.GET("/api/v1/schedules");
  if (error || !data) throw new Error("Failed to load schedules");
  return data.items;
}

export async function createSchedule(
  body: ScheduleWriteBody,
): Promise<ScheduleOut> {
  const { data, error } = await client.POST("/api/v1/schedules", { body });
  if (error || !data) throw new Error("Failed to create schedule");
  return data;
}

export async function updateSchedule(
  scheduleId: string,
  body: ScheduleWriteBody,
): Promise<ScheduleOut> {
  const { data, error } = await client.PUT("/api/v1/schedules/{schedule_id}", {
    params: { path: { schedule_id: scheduleId } },
    body,
  });
  if (error || !data) throw new Error("Failed to update schedule");
  return data;
}

export async function deleteSchedule(scheduleId: string): Promise<void> {
  const { error } = await client.DELETE("/api/v1/schedules/{schedule_id}", {
    params: { path: { schedule_id: scheduleId } },
  });
  if (error) throw new Error("Failed to delete schedule");
}

export function useSchedules() {
  return useQuery({
    queryKey: SCHEDULES_QUERY_KEY,
    queryFn: listSchedules,
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: SCHEDULES_QUERY_KEY }),
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ScheduleWriteBody }) =>
      updateSchedule(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: SCHEDULES_QUERY_KEY }),
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: SCHEDULES_QUERY_KEY }),
  });
}
