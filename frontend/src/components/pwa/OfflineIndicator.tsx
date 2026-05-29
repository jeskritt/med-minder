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
      className="bg-amber-500 px-4 py-1.5 text-center text-sm font-medium text-amber-950"
    >
      You're offline. Live data will load again once you reconnect.
    </div>
  );
}
