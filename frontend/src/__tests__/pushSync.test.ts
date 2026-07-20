// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  client: { POST: vi.fn(async () => ({ error: undefined })) },
}));

import { client } from "@/lib/api";
import { syncPushSubscription } from "@/lib/push";

const mockPost = vi.mocked(client.POST);

const SUBSCRIPTION = {
  endpoint: "https://fcm.googleapis.com/fcm/send/abc",
  toJSON: () => ({ keys: { p256dh: "p256dh-value", auth: "auth-value" } }),
};

/** Install the browser push APIs `syncPushSubscription` depends on. */
function stubBrowser(options: {
  permission: NotificationPermission;
  subscription: unknown;
}) {
  const subscribe = vi.fn();
  Object.defineProperty(globalThis, "Notification", {
    configurable: true,
    value: { permission: options.permission },
  });
  Object.defineProperty(globalThis, "PushManager", {
    configurable: true,
    value: class {},
  });
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      ready: Promise.resolve({
        pushManager: {
          getSubscription: async () => options.subscription,
          subscribe,
        },
      }),
    },
  });
  return { subscribe };
}

describe("syncPushSubscription", () => {
  beforeEach(() => vi.clearAllMocks());

  it("re-registers an existing browser subscription with the backend", async () => {
    stubBrowser({ permission: "granted", subscription: SUBSCRIPTION });
    await syncPushSubscription();
    expect(mockPost).toHaveBeenCalledWith("/api/v1/push/subscriptions", {
      body: {
        endpoint: SUBSCRIPTION.endpoint,
        keys: { p256dh: "p256dh-value", auth: "auth-value" },
      },
    });
  });

  it("never calls subscribe() — it only mirrors what the browser holds", async () => {
    const { subscribe } = stubBrowser({
      permission: "granted",
      subscription: SUBSCRIPTION,
    });
    await syncPushSubscription();
    expect(subscribe).not.toHaveBeenCalled();
  });

  it("does nothing when this device has no subscription", async () => {
    stubBrowser({ permission: "granted", subscription: null });
    await syncPushSubscription();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("does not prompt or register when permission was not granted", async () => {
    stubBrowser({ permission: "default", subscription: SUBSCRIPTION });
    await syncPushSubscription();
    expect(mockPost).not.toHaveBeenCalled();
  });
});
