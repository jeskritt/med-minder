import {
  useDisablePush,
  useEnablePush,
  usePushStatus,
} from "@/hooks/usePushSubscription";

/**
 * Minimal "Enable notifications" control (Phase 7). The polished permission
 * onboarding flow is Phase 8; this is just enough to register a device and
 * test the loop. Reminders are visible in-app regardless of this state.
 *
 * The "on" state tracks an actual push subscription, not the browser
 * permission — a `granted` device with no subscription can't receive anything,
 * so it falls through to the enable button to re-subscribe.
 */
export function EnableNotifications() {
  const { data: status } = usePushStatus();
  const enable = useEnablePush();
  const disable = useDisablePush();

  if (status === "unsupported") {
    return (
      <p className="text-sm text-slate-500">
        This browser does not support notifications. Reminders still appear
        below.
      </p>
    );
  }

  if (status === "denied") {
    return (
      <p className="text-sm text-amber-700">
        Notifications are blocked in your browser settings. Reminders still
        appear below.
      </p>
    );
  }

  if (status === "subscribed") {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="text-green-700">
          Notifications are on for this device.
        </span>
        <button
          type="button"
          onClick={() => disable.mutate()}
          disabled={disable.isPending}
          className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          {disable.isPending ? "Turning off…" : "Turn off"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 text-sm">
      <button
        type="button"
        onClick={() => enable.mutate()}
        disabled={enable.isPending}
        className="self-start rounded-lg bg-blue-600 px-3 py-1.5 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {enable.isPending ? "Enabling…" : "Enable notifications"}
      </button>
      {enable.isError && (
        <span className="text-amber-700">
          {enable.error instanceof Error
            ? enable.error.message
            : "Could not enable notifications."}
        </span>
      )}
    </div>
  );
}
