import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { formatElapsed, tickFrom } from "@/lib/timers";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

interface CountUpCase {
  name: string;
  med: { timer_preference: "count_up" };
  doses: { taken_at: string }[];
  now: string;
  expected: {
    mode: "count_up";
    last_dose_at: string | null;
    count_up: { elapsed_seconds: number | null };
  };
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.resolve(
  __dirname,
  "../../../backend/tests/domain/fixtures/timer_cases.json",
);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as {
  count_up: CountUpCase[];
};

describe("formatElapsed", () => {
  it.each(fixture.count_up)(
    "$name: produces the expected display string",
    (c: CountUpCase) => {
      const seconds = c.expected.count_up.elapsed_seconds;
      const rendered = formatElapsed(seconds ?? null);
      if (seconds === null) {
        expect(rendered).toBe("no doses recorded yet");
      } else if (seconds > 86_400) {
        expect(rendered).toBe("over 24h ago");
      } else if (seconds < 3600) {
        expect(rendered).toBe(`${Math.floor(seconds / 60)}m ago`);
      } else {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        expect(rendered).toBe(`${h}h ${m}m ago`);
      }
    },
  );

  it("renders no doses for null", () => {
    expect(formatElapsed(null)).toBe("no doses recorded yet");
  });

  it("caps at over 24h ago", () => {
    expect(formatElapsed(86_401)).toBe("over 24h ago");
    expect(formatElapsed(86_400)).not.toBe("over 24h ago");
  });
});

describe("tickFrom", () => {
  it("advances elapsed_seconds by the wall-clock delta", () => {
    const state: TimerStateOut = {
      mode: "count_up",
      as_of: "2026-05-14T12:00:00Z",
      last_dose_at: "2026-05-14T11:57:00Z",
      count_up: { elapsed_seconds: 180 },
    };
    const asOfMs = Date.parse(state.as_of);
    const ticked = tickFrom(state, asOfMs + 60_000);
    expect(ticked.count_up?.elapsed_seconds).toBe(240);
  });

  it("never goes backwards on monotonic clock skew", () => {
    const state: TimerStateOut = {
      mode: "count_up",
      as_of: "2026-05-14T12:00:00Z",
      last_dose_at: "2026-05-14T11:57:00Z",
      count_up: { elapsed_seconds: 180 },
    };
    const asOfMs = Date.parse(state.as_of);
    const ticked = tickFrom(state, asOfMs - 10_000);
    expect(ticked.count_up?.elapsed_seconds).toBe(180);
  });

  it("passes null elapsed through unchanged", () => {
    const state: TimerStateOut = {
      mode: "count_up",
      as_of: "2026-05-14T12:00:00Z",
      last_dose_at: null,
      count_up: { elapsed_seconds: null },
    };
    const ticked = tickFrom(state, Date.parse(state.as_of) + 60_000);
    expect(ticked.count_up?.elapsed_seconds).toBeNull();
  });
});
