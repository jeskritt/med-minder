import { useState } from "react";
import { Bell, Check } from "lucide-react";

import {
  useDisablePush,
  useEnablePush,
  usePushStatus,
} from "@/hooks/usePushSubscription";

/**
 * Push-notification control (Phase 8 / FR-010–013).
 *
 * Polished permission UX over the Phase 7 subscription flow: a plain-language
 * pre-prompt precedes the browser's native permission dialog, and every push
 * state has clear guidance (incl. how to recover from a blocked/denied state).
 * The "on" state tracks an actual subscription, not just browser permission —
 * a `granted` device with no subscription still falls through to enable.
 * Reminders remain visible in-app regardless of this state.
 */
export function EnableNotifications() {
  const { data: status } = usePushStatus();
  const enable = useEnablePush();
  const disable = useDisablePush();
  const [showPrompt, setShowPrompt] = useState(false);

  if (status === "unsupported") {
    return (
      <p className="text-sm text-muted-foreground">
        This browser does not support notifications. Your reminders still appear
        in the list below.
      </p>
    );
  }

  if (status === "denied") {
    return (
      <div className="flex flex-col gap-1 text-sm text-warning-foreground">
        <p className="font-semibold">
          Notifications are blocked for this site.
        </p>
        <p className="text-warning-foreground/90">
          To turn them on, open your browser's site settings (the lock or
          &ldquo;aA&rdquo; icon in the address bar) → Notifications → Allow,
          then reload this page. Your reminders still appear in the list below
          in the meantime.
        </p>
      </div>
    );
  }

  if (status === "subscribed") {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="inline-flex items-center gap-1.5 font-medium text-success">
          <Check className="size-4" />
          Notifications are on for this device.
        </span>
        <button
          type="button"
          onClick={() => disable.mutate()}
          disabled={disable.isPending}
          className="mm-btn mm-btn-secondary mm-btn-sm"
        >
          {disable.isPending ? "Turning off…" : "Turn off"}
        </button>
      </div>
    );
  }

  // status: "default" | "unsubscribed" — offer enablement, with a contextual
  // pre-prompt before the native permission dialog (FR-010).
  if (!showPrompt) {
    return (
      <div className="flex flex-col gap-1 text-sm">
        <button
          type="button"
          onClick={() => setShowPrompt(true)}
          className="mm-btn mm-btn-primary self-start"
        >
          <Bell className="size-4" />
          Enable notifications
        </button>
      </div>
    );
  }

  return (
    <div className="flex max-w-md flex-col gap-3 text-sm">
      <p className="text-foreground">
        MedMinder will send a notification at each scheduled dose time so you
        don't miss a medication. You can turn this off any time. Your browser
        will ask for permission next.
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => enable.mutate()}
          disabled={enable.isPending}
          className="mm-btn mm-btn-primary"
        >
          {enable.isPending ? "Enabling…" : "Turn on reminders"}
        </button>
        <button
          type="button"
          onClick={() => setShowPrompt(false)}
          disabled={enable.isPending}
          className="mm-btn mm-btn-ghost"
        >
          Not now
        </button>
      </div>
      {enable.isError && (
        <span className="text-warning-foreground">
          {enable.error instanceof Error
            ? enable.error.message
            : "Could not enable notifications."}
        </span>
      )}
    </div>
  );
}
