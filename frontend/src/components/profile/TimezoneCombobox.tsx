import { useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

const INPUT_CLASS = "mm-input mt-1";

/** Cap the rendered option list — the full IANA set is ~400 entries. */
const MAX_RESULTS = 50;

/**
 * Friendly regional/province/state keywords for common IANA zones whose
 * canonical city name differs from what users search for (e.g. "Alberta" or
 * "Calgary" → "America/Edmonton").
 */
const SEARCH_ALIASES: Record<string, string> = {
  "America/Edmonton": "alberta calgary ab mountain",
  "America/Regina": "saskatchewan saskatoon sk",
  "America/Vancouver": "british columbia victoria bc pacific",
  "America/Winnipeg": "manitoba mb central",
  "America/Toronto": "ontario ottawa montreal quebec on qc eastern",
  "America/Halifax": "nova scotia new brunswick pei atlantic ns nb",
  "America/St_Johns": "newfoundland labrador nl",
  "America/New_York": "eastern est edt",
  "America/Chicago": "central cst cdt",
  "America/Denver": "mountain mst mdt",
  "America/Los_Angeles": "pacific pst pdt california",
  "America/Phoenix": "arizona",
  "America/Anchorage": "alaska",
  "Pacific/Honolulu": "hawaii",
  UTC: "utc gmt coordinated universal time",
};

interface ZoneOption {
  id: string;
  offset: string;
  searchText: string;
}

/** Format a zone's current UTC offset (e.g. "UTC-6", "UTC+5:30", "UTC+0"). */
function formatUtcOffset(tz: string, referenceDate: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      timeZoneName: "shortOffset",
    }).formatToParts(referenceDate);
    const raw = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
    if (!raw) return "";
    if (raw === "GMT" || raw === "UTC") return "UTC+0";
    return raw.replace(/^GMT/, "UTC");
  } catch {
    return "";
  }
}

/** All IANA zone names (plus UTC), or `[]` if the runtime lacks `Intl.supportedValuesOf`. */
function allTimeZones(): string[] {
  const fn = (Intl as { supportedValuesOf?: (key: string) => string[] })
    .supportedValuesOf;
  try {
    const raw = fn ? fn("timeZone") : [];
    if (raw.length === 0) return [];
    return raw.includes("UTC") ? raw : ["UTC", ...raw];
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
 * (e.g. "Edmo", "Alberta", or "UTC-6") and the list narrows by case-insensitive
 * substring across zone IDs, friendly aliases, and current UTC offsets.  It
 * only ever commits a value drawn from the valid list — typing free text and
 * blurring reverts to the last committed value — so an invalid zone can never
 * be submitted.
 */
export function TimezoneCombobox({
  value,
  onChange,
  id,
}: TimezoneComboboxProps) {
  const reactId = useId();
  const inputId = id ?? `tz-${reactId}`;
  const listId = `${inputId}-list`;

  const zones = useMemo<ZoneOption[]>(() => {
    const all = allTimeZones();
    // Guarantee the current value stays selectable even on a runtime without
    // the Intl list (older browsers, some test environments).
    const ids =
      all.length > 0
        ? value && !all.includes(value)
          ? [value, ...all]
          : all
        : value
          ? [value]
          : [];
    const now = new Date();
    return ids.map((zoneId) => {
      const offset = formatUtcOffset(zoneId, now);
      const alias = SEARCH_ALIASES[zoneId] ?? "";
      const gmtOffset = offset.replace(/^UTC/, "GMT");
      const searchText = [
        zoneId,
        zoneId.replace(/_/g, " "),
        offset,
        gmtOffset,
        alias,
      ]
        .join(" ")
        .toLowerCase();
      return { id: zoneId, offset, searchText };
    });
  }, [value]);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [isFiltering, setIsFiltering] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Reflect the committed value in the field when it changes externally (e.g.
  // /me resolving after first render). Render-phase reconciliation, not an
  // effect — React's "adjusting state when a prop changes" pattern.
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setQuery(value);
    setIsFiltering(false);
  }

  const matches = useMemo(() => {
    const q = isFiltering ? query.trim().toLowerCase() : "";
    const pool =
      q === "" ? zones : zones.filter((z) => z.searchText.includes(q));
    return pool.slice(0, MAX_RESULTS);
  }, [isFiltering, query, zones]);

  function commit(tz: string) {
    onChange(tz);
    setQuery(tz);
    setIsFiltering(false);
    setOpen(false);
  }

  /** Leaving the field: accept an exact (case-insensitive) typed match, else
   *  snap back to the committed value so the control never holds junk. */
  function handleBlur() {
    const q = query.trim().toLowerCase();
    const exact = zones.find((z) => z.id.toLowerCase() === q);
    if (exact) commit(exact.id);
    else {
      setQuery(value);
      setIsFiltering(false);
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
      setHighlight((h) => Math.min(h + 1, Math.max(matches.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (open && matches[highlight]) {
        e.preventDefault();
        commit(matches[highlight].id);
      }
    } else if (e.key === "Escape") {
      setQuery(value);
      setIsFiltering(false);
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
          const next = e.target.value;
          setQuery(next);
          setIsFiltering(true);
          setOpen(true);
          setHighlight(0);
          // Commit immediately on an exact IANA match so Save enables without
          // forcing an extra click or blur first.
          const exact = zones.find(
            (z) => z.id.toLowerCase() === next.trim().toLowerCase(),
          );
          if (exact) {
            onChange(exact.id);
          }
        }}
        onFocus={(e) => {
          setOpen(true);
          setIsFiltering(false);
          setHighlight(0);
          e.currentTarget.select();
        }}
        onKeyDown={onKeyDown}
        onBlur={handleBlur}
      />
      {open && matches.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-border bg-popover shadow-lg"
        >
          {matches.map((z, i) => (
            <li
              key={z.id}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={z.id === value}
              // Keep the input focused so onClick selects before onBlur reverts.
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setHighlight(i)}
              onClick={() => commit(z.id)}
              className={`flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm ${
                i === highlight
                  ? "bg-primary text-primary-foreground"
                  : "text-popover-foreground"
              }`}
            >
              <span>{z.id}</span>
              {z.offset && (
                <>
                  {" "}
                  <span
                    className={`shrink-0 text-xs ${
                      i === highlight
                        ? "text-primary-foreground/80"
                        : "text-muted-foreground"
                    }`}
                  >
                    {z.offset}
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
