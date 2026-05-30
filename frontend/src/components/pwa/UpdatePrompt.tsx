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
    <div className="flex items-center justify-center gap-3 bg-primary px-4 py-2 text-sm text-primary-foreground">
      <span>A new version of MedMinder is available.</span>
      <button
        type="button"
        onClick={() => applyPendingUpdate()}
        className="rounded-full bg-primary-foreground/20 px-3 py-1 font-semibold transition hover:bg-primary-foreground/30"
      >
        Refresh
      </button>
    </div>
  );
}
