import { useEffect, useState } from "react";

import { applyPendingUpdate, onUpdateAvailable } from "@/lib/pwa";

/**
 * "New version available" prompt (Phase 8 / FR-008).
 *
 * vite-plugin-pwa is configured with `registerType: 'prompt'`, so a freshly
 * deployed shell waits until the user clicks Refresh — a controlled update with
 * no automatic reload loop.
 */
export function UpdatePrompt() {
  const [available, setAvailable] = useState(false);

  useEffect(() => onUpdateAvailable(() => setAvailable(true)), []);

  if (!available) return null;

  return (
    <div className="flex items-center justify-center gap-3 bg-blue-600 px-4 py-1.5 text-sm text-white">
      <span>A new version of MedMinder is available.</span>
      <button
        type="button"
        onClick={() => applyPendingUpdate()}
        className="rounded bg-white/20 px-3 py-1 font-medium hover:bg-white/30"
      >
        Refresh
      </button>
    </div>
  );
}
