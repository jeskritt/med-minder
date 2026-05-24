/**
 * Push enablement hooks (Phase 7): permission state + enable/disable.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disablePushNotifications,
  enablePushNotifications,
  getPushPermissionState,
  type PushPermission,
} from "@/lib/push";

export const PUSH_PERMISSION_QUERY_KEY = ["push-permission"] as const;

export function usePushPermission() {
  return useQuery<PushPermission>({
    queryKey: PUSH_PERMISSION_QUERY_KEY,
    queryFn: () => getPushPermissionState(),
    staleTime: 5_000,
  });
}

export function useEnablePush() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: enablePushNotifications,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: PUSH_PERMISSION_QUERY_KEY }),
  });
}

export function useDisablePush() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disablePushNotifications,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: PUSH_PERMISSION_QUERY_KEY }),
  });
}
