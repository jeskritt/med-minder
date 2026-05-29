/// <reference lib="webworker" />
/**
 * MedMinder service worker (Phase 8 — PWA polish).
 *
 * Authored worker built via vite-plugin-pwa's injectManifest strategy: Workbox
 * precaches the static app shell and serves index.html for offline SPA
 * navigations, while the Phase 7 Web Push handlers are preserved and extended
 * with Snooze / Mark-taken notification actions (FR-014/015).
 *
 * Caching policy: ONLY the static shell is precached. `/api` is never matched
 * by a runtime route and never listed in the precache manifest, so no medical
 * data is ever stored in the cache (FR-006 / SC-004).
 */
import { createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<string | { url: string; revision: string | null }>;
};

// Injected by vite-plugin-pwa at build time — the hashed static shell assets.
precacheAndRoute(self.__WB_MANIFEST);

// Offline app shell: SPA navigations fall back to the precached index.html.
// `/api` is excluded so API calls always hit the network and are never cached.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("index.html"), {
    denylist: [/^\/api\//],
  }),
);

// Controlled update (FR-008): vite-plugin-pwa's `updateSW(true)` (behind the
// UpdatePrompt's "Refresh") posts SKIP_WAITING to the waiting worker. An
// injectManifest worker must handle it — activate immediately so the page can
// reload onto the new version (generateSW would inject this; we author it).
self.addEventListener("message", (event: ExtendableMessageEvent) => {
  const message = event.data as { type?: string } | undefined;
  if (message?.type === "SKIP_WAITING") {
    void self.skipWaiting();
  }
});

interface ReminderPushData {
  reminder_id?: string;
  type?: "dose" | "refill";
  title?: string;
  body?: string;
}

// Notification action buttons are widely supported but not in this TS release's
// lib.webworker `NotificationOptions`; extend it locally.
interface NotificationActionOption {
  action: string;
  title: string;
  icon?: string;
}
interface ExtendedNotificationOptions extends NotificationOptions {
  actions?: NotificationActionOption[];
}

function parsePushData(event: PushEvent): ReminderPushData {
  try {
    return event.data ? (event.data.json() as ReminderPushData) : {};
  } catch {
    return {};
  }
}

self.addEventListener("push", (event: PushEvent) => {
  const data = parsePushData(event);
  const title = data.title ?? "MedMinder";
  const isDose = data.type === "dose";
  const options: ExtendedNotificationOptions = {
    body: data.body ?? "Time for your medication.",
    tag: data.reminder_id,
    data,
    // Dose reminders carry quick actions so the user can act without opening
    // the app (FR-014); refill reminders just open the app on tap.
    actions: isDose
      ? [
          { action: "snooze", title: "Snooze 1h" },
          { action: "take", title: "Mark taken" },
        ]
      : [],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

async function openApp(): Promise<void> {
  const windows = await self.clients.matchAll({
    type: "window",
    includeUncontrolled: true,
  });
  for (const client of windows) {
    if ("focus" in client) {
      await client.focus();
      return;
    }
  }
  await self.clients.openWindow("/reminders");
}

async function notifyOpenApp(message: string): Promise<void> {
  await self.registration.showNotification("MedMinder", {
    body: message,
    tag: "mm-action-failed",
  });
}

async function actOnReminder(
  reminderId: string,
  action: "snooze" | "take",
): Promise<void> {
  // Same-origin fetch carries the mm_session cookie (SameSite=Lax). The take
  // endpoint records a dose per attached med atomically and resolves the
  // reminder; on any guard block / error it returns non-2xx, so we fail safe
  // by telling the user to open the app (FR-015/FR-016).
  try {
    const response = await fetch(`/api/v1/reminders/${reminderId}/${action}`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      await notifyOpenApp(
        action === "take"
          ? "Couldn't record your dose — open MedMinder to finish."
          : "Couldn't snooze — open MedMinder to try again.",
      );
    }
  } catch {
    await notifyOpenApp("You appear to be offline — open MedMinder to retry.");
  }
}

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const data = (event.notification.data ?? {}) as ReminderPushData;
  const reminderId = data.reminder_id;

  if (reminderId && (event.action === "snooze" || event.action === "take")) {
    event.waitUntil(actOnReminder(reminderId, event.action));
    return;
  }
  // Body tap (or unknown action): open the app (Phase 7 behavior preserved).
  event.waitUntil(openApp());
});
