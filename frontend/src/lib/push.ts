/**
 * Web Push enablement helpers (Phase 7 — minimal; Phase 8 polishes the UX).
 *
 * Requests browser permission, registers the minimal service worker
 * (`/sw.js`), subscribes via the PushManager using the server's VAPID public
 * key, and registers the subscription with the backend. Push is best-effort:
 * reminders are always visible in-app regardless (FR-003 / FR-008).
 */

import { client } from "@/lib/api";

/**
 * Notification control state. Distinct from the raw browser *permission*: a
 * device can have permission `granted` yet hold no push subscription (a cleared
 * or failed/partial subscribe), in which case nothing can be delivered. The UI
 * keys off this, not permission alone.
 */
export type PushStatus =
  | "unsupported"
  | "denied"
  | "default"
  | "subscribed"
  | "unsubscribed";

export function isPushSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    "serviceWorker" in navigator &&
    typeof window !== "undefined" &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export async function getPushStatus(): Promise<PushStatus> {
  if (!isPushSupported()) return "unsupported";
  const permission = Notification.permission;
  if (permission !== "granted") return permission; // "default" | "denied"
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  return subscription ? "subscribed" : "unsubscribed";
}

/** Convert a URL-safe-base64 VAPID key to the bytes PushManager expects.
 *
 * Backed by an explicit ArrayBuffer (not the default ArrayBufferLike) so the
 * result satisfies `BufferSource` for `applicationServerKey`. */
function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  const buffer = new ArrayBuffer(raw.length);
  const output = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

async function fetchVapidPublicKey(): Promise<string> {
  const { data, error } = await client.GET("/api/v1/push/vapid-public-key");
  if (error || !data) {
    throw new Error("Could not load the notification key.");
  }
  return data.public_key;
}

export async function enablePushNotifications(): Promise<void> {
  if (!isPushSupported()) {
    throw new Error("This browser does not support notifications.");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Notification permission was not granted.");
  }
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const publicKey = await fetchVapidPublicKey();
  if (!publicKey) {
    throw new Error("Notifications are not configured on the server yet.");
  }
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });
  const keys = subscription.toJSON().keys;
  if (!keys?.p256dh || !keys?.auth) {
    throw new Error("The browser subscription is missing its keys.");
  }
  const { error } = await client.POST("/api/v1/push/subscriptions", {
    body: {
      endpoint: subscription.endpoint,
      keys: { p256dh: keys.p256dh, auth: keys.auth },
    },
  });
  if (error) {
    throw new Error("Could not register this device for notifications.");
  }
}

export async function disablePushNotifications(): Promise<void> {
  if (!isPushSupported()) return;
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return;
  await client.DELETE("/api/v1/push/subscriptions", {
    body: { endpoint: subscription.endpoint },
  });
  await subscription.unsubscribe();
}
