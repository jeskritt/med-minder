import { useEffect, useState } from "react";

/**
 * Offline indicator (Phase 8 / FR-005/007).
 *
 * App-shell-only PWA: when offline, the shell still renders (precached) but no
 * API data is cached. This banner is the global "you're offline" cue; data
 * views surface their own offline/error state on the failed fetch.
 */
export function OfflineIndicator() {
  const [offline, setOffline] = useState(
    typeof navigator !== "undefined" && navigator.onLine === false,
  );

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="bg-warning px-4 py-2 text-center text-sm font-medium text-warning-foreground"
    >
      You're offline. Live data will load again once you reconnect.
    </div>
  );
}
