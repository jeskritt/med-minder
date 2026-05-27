import { useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30";

/** Cap the rendered option list — the full IANA set is ~400 entries. */
const MAX_RESULTS = 50;

/** All IANA zone names, or `[]` if the runtime lacks `Intl.supportedValuesOf`. */
function allTimeZones(): string[] {
  const fn = (Intl as { supportedValuesOf?: (key: string) => string[] })
    .supportedValuesOf;
  try {
    return fn ? fn("timeZone") : [];
  } catch {
    return [];
  }
}

export interface TimezoneComboboxProps {
  value: string;
  onChange: (tz: string) => void;
  id?: string;
}

/**
 * A dependency-free, searchable timezone picker.  The user types a fragment
 * (e.g. "Edmo") and the list narrows by case-insensitive **substring** to
 * matching IANA zones ("America/Edmonton").  It only ever commits a value
 * drawn from the valid list — typing free text and blurring reverts to the
 * last committed value — so an invalid zone can never be submitted.
 */
export function TimezoneCombobox({
  value,
  onChange,
  id,
}: TimezoneComboboxProps) {
  const reactId = useId();
  const inputId = id ?? `tz-${reactId}`;
  const listId = `${inputId}-list`;

  const zones = useMemo(() => {
    const all = allTimeZones();
    // Guarantee the current value stays selectable even on a runtime without
    // the Intl list (older browsers, some test environments).
    return all.length > 0 ? all : value ? [value] : [];
  }, [value]);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Reflect the committed value in the field when it changes externally (e.g.
  // /me resolving after first render). Render-phase reconciliation, not an
  // effect — React's "adjusting state when a prop changes" pattern.
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setQuery(value);
  }

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool =
      q === "" ? zones : zones.filter((z) => z.toLowerCase().includes(q));
    return pool.slice(0, MAX_RESULTS);
  }, [query, zones]);

  function commit(tz: string) {
    onChange(tz);
    setQuery(tz);
    setOpen(false);
  }

  /** Leaving the field: accept an exact (case-insensitive) typed match, else
   *  snap back to the committed value so the control never holds junk. */
  function handleBlur() {
    const q = query.trim().toLowerCase();
    const exact = zones.find((z) => z.toLowerCase() === q);
    if (exact) commit(exact);
    else {
      setQuery(value);
      setOpen(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlight((h) => Math.min(h + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (open && matches[highlight]) {
        e.preventDefault();
        commit(matches[highlight]);
      }
    } else if (e.key === "Escape") {
      setQuery(value);
      setOpen(false);
    }
  }

  const activeId =
    open && matches[highlight] ? `${listId}-opt-${highlight}` : undefined;

  return (
    <div ref={containerRef} className="relative">
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        autoComplete="off"
        className={INPUT_CLASS}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHighlight(0);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        onBlur={handleBlur}
      />
      {open && matches.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow"
        >
          {matches.map((z, i) => (
            <li
              key={z}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={z === value}
              // Keep the input focused so onClick selects before onBlur reverts.
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setHighlight(i)}
              onClick={() => commit(z)}
              className={`cursor-pointer px-3 py-1.5 text-sm ${
                i === highlight ? "bg-blue-600 text-white" : "text-slate-700"
              }`}
            >
              {z}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
