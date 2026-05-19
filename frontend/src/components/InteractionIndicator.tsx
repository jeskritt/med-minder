import { useEffect, useState } from "react";
import { formatRemaining } from "@/lib/timers";
import type { components } from "@/api/v1";

type InteractionStateOut = components["schemas"]["InteractionStateOut"];

export interface InteractionIndicatorProps {
  state: InteractionStateOut;
}

/**
 * Phase 6 (FR-012/FR-013): human-readable active-interaction status
 * with a live remaining time. Same client-counter approach as the
 * Phase 5 timer displays — a local 1s tick seeded from the
 * server-authoritative `as_of`; no polling. The indicator clears when
 * the server stops returning `interaction_state` (cooldown elapsed or
 * arming dose voided) on the next refetch.
 */
export function InteractionIndicator({ state }: InteractionIndicatorProps) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [state.as_of, state.remaining_seconds]);

  const elapsed = Math.max(
    0,
    Math.floor((nowMs - Date.parse(state.as_of)) / 1000),
  );
  const remaining = Math.max(0, state.remaining_seconds - elapsed);
  const names = state.conflicts
    .map((c) => c.conflicting_medication_name)
    .join(", ");

  return (
    <p role="status" className="text-sm text-amber-700">
      Interacts with {names} — safe in {formatRemaining(remaining)}
    </p>
  );
}
