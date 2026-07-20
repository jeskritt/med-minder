/**
 * Push enablement hooks (Phase 7): permission state + enable/disable.
 */

import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disablePushNotifications,
  enablePushNotifications,
  getPushStatus,
  syncPushSubscription,
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

/**
 * Re-register this device's push subscription with the backend once per
 * session, so a server-side subscription the browser doesn't know it lost is
 * silently restored. Fire-and-forget: failures are swallowed rather than
 * surfaced, since this is a repair path the user never asked for.
 *
 * Pass `enabled: false` while unauthenticated — the endpoint is auth-gated.
 */
export function useSyncPushSubscription(enabled: boolean): void {
  const done = useRef(false);
  useEffect(() => {
    if (!enabled || done.current) return;
    done.current = true;
    void syncPushSubscription().catch(() => {
      // Best-effort repair; the in-app reminder list works regardless.
    });
  }, [enabled]);
}

export function useDisablePush() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disablePushNotifications,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: PUSH_STATUS_QUERY_KEY }),
  });
}
