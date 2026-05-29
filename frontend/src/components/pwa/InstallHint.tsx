import { useState } from "react";

/**
 * iOS "Add to Home Screen" hint (Phase 8 / FR-002).
 *
 * iOS Safari has no programmatic install prompt, so we show a dismissable tip
 * — but only on iOS Safari and only when the app is not already running
 * standalone. Android/desktop use the browser's native install affordance and
 * never see this.
 */
const DISMISS_KEY = "mm-install-hint-dismissed";

function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const nav = navigator as Navigator & { standalone?: boolean };
  if (nav.standalone === true) return true;
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(display-mode: standalone)").matches
  );
}

export function InstallHint() {
  const [show, setShow] = useState(() => {
    if (typeof window === "undefined") return false;
    const dismissed = localStorage.getItem(DISMISS_KEY) === "1";
    return isIos() && !isStandalone() && !dismissed;
  });

  if (!show) return null;

  return (
    <div className="flex items-start gap-3 bg-slate-900 px-4 py-2 text-sm text-slate-100">
      <p className="flex-1">
        Install MedMinder: tap the Share icon, then{" "}
        <span className="font-medium">Add to Home Screen</span>.
      </p>
      <button
        type="button"
        aria-label="Dismiss install hint"
        onClick={() => {
          localStorage.setItem(DISMISS_KEY, "1");
          setShow(false);
        }}
        className="rounded px-2 font-medium text-slate-300 hover:text-white"
      >
        Dismiss
      </button>
    </div>
  );
}
