/*
 * MedMinder minimal service worker (Phase 7).
 *
 * Just enough to display delivered Web Push notifications and focus the app
 * when one is tapped. Phase 8 (PWA polish) replaces this with a
 * vite-plugin-pwa-managed worker (offline shell, etc.).
 */

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const title = data.title || "MedMinder";
  const options = {
    body: data.body || "Time for your medication.",
    tag: data.reminder_id || undefined,
    data,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      for (const client of windows) {
        if ("focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow("/reminders");
      }
      return undefined;
    })(),
  );
});
