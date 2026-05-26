/**
 * Push enablement hooks (Phase 7): permission state + enable/disable.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disablePushNotifications,
  enablePushNotifications,
  getPushStatus,
  type PushStatus,
} from "@/lib/push";

export const PUSH_STATUS_QUERY_KEY = ["push-status"] as const;

export function usePushStatus() {
  return useQuery<PushStatus>({
    queryKey: PUSH_STATUS_QUERY_KEY,
    queryFn: () => getPushStatus(),
    staleTime: 5_000,
  });
}

export function useEnablePush() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: enablePushNotifications,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: PUSH_STATUS_QUERY_KEY }),
  });
}

export function useDisablePush() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disablePushNotifications,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: PUSH_STATUS_QUERY_KEY }),
  });
}
