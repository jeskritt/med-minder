/**
 * PWA service-worker registration (Phase 8).
 *
 * Wraps vite-plugin-pwa's `virtual:pwa-register`. We register manually (rather
 * than auto-injecting) so an update is applied only when the user clicks the
 * UpdatePrompt — a controlled refresh with no auto-reload loop (FR-008).
 */
import { registerSW } from "virtual:pwa-register";

let applyUpdate: (() => Promise<void>) | null = null;
let updateReady = false;
const listeners = new Set<() => void>();

/** Register the service worker once at app startup (call from main.tsx). */
export function initPwa(): void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }
  const update = registerSW({
    immediate: true,
    onNeedRefresh() {
      applyUpdate = async () => {
        await update(true);
      };
      updateReady = true;
      for (const listener of listeners) listener();
    },
  });
}

/**
 * Subscribe to "a new version is waiting" events. Fires immediately if an
 * update is already pending (so a late-mounting component never misses it).
 * Returns an unsubscribe function.
 */
export function onUpdateAvailable(listener: () => void): () => void {
  listeners.add(listener);
  if (updateReady) listener();
  return () => {
    listeners.delete(listener);
  };
}

/** Apply the waiting worker and reload (called from the UpdatePrompt button). */
export function applyPendingUpdate(): void {
  void applyUpdate?.();
}
