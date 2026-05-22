import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, it, expect } from "vitest";
import {
  formatElapsed,
  formatRemaining,
  tickFrom,
  windowProgress,
} from "@/lib/timers";
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

interface CountDownCase {
  name: string;
  med: { timer_preference: "count_down"; min_interval_minutes: number };
  doses: { taken_at: string }[];
  now: string;
  expected: {
    mode: "count_down";
    last_dose_at: string | null;
    count_down: {
      min_interval_seconds: number;
      next_allowed_at: string | null;
      remaining_seconds: number;
    };
  };
}

interface MultiSubDoseCase {
  name: string;
  med: {
    timer_preference: "multi_sub_dose";
    window_duration_minutes: number;
    times_per_day: number;
  };
  doses: { taken_at: string }[];
  now: string;
  expected: {
    mode: "multi_sub_dose";
    last_dose_at: string | null;
    multi_sub_dose: {
      window_duration_seconds: number;
      max_concurrent: number;
      active_sub_doses: { taken_at: string; expires_at: string }[];
      slots_used: number;
      slots_remaining: number;
      next_available_at: string | null;
    };
  };
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.resolve(
  __dirname,
  "../../../backend/tests/domain/fixtures/timer_cases.json",
);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as {
  count_up: CountUpCase[];
  count_down: CountDownCase[];
  multi_sub_dose: MultiSubDoseCase[];
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

describe("formatRemaining", () => {
  it.each(fixture.count_down)(
    "$name: produces a string the UI can render",
    (c: CountDownCase) => {
      const seconds = c.expected.count_down.remaining_seconds;
      const rendered = formatRemaining(seconds);
      if (seconds <= 0) {
        expect(rendered).toBe("ready");
      } else if (seconds < 60) {
        expect(rendered).toBe("<1m");
      } else if (seconds < 3600) {
        expect(rendered).toBe(`${Math.floor(seconds / 60)}m`);
      } else {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        expect(rendered).toBe(`${h}h ${m}m`);
      }
    },
  );

  it("renders 'ready' at zero or below", () => {
    expect(formatRemaining(0)).toBe("ready");
    expect(formatRemaining(-5)).toBe("ready");
  });

  it("renders '<1m' under 60 seconds", () => {
    expect(formatRemaining(1)).toBe("<1m");
    expect(formatRemaining(59)).toBe("<1m");
  });

  it("renders minutes-only under one hour", () => {
    expect(formatRemaining(60)).toBe("1m");
    expect(formatRemaining(3000)).toBe("50m");
  });

  it("renders Xh Ym at one hour or more", () => {
    expect(formatRemaining(3600)).toBe("1h 0m");
    expect(formatRemaining(7140)).toBe("1h 59m");
  });
});

describe("windowProgress", () => {
  it.each(fixture.multi_sub_dose)(
    "$name: reports used/total/remaining/nextAvailableAt",
    (c: MultiSubDoseCase) => {
      const p = c.expected.multi_sub_dose;
      const state: TimerStateOut = {
        mode: "multi_sub_dose",
        as_of: c.now,
        last_dose_at: c.expected.last_dose_at,
        multi_sub_dose: p,
      };
      expect(windowProgress(state)).toEqual({
        used: p.slots_used,
        total: p.max_concurrent,
        remaining: p.slots_remaining,
        nextAvailableAt: p.next_available_at,
      });
    },
  );

  it("returns zeros for a non-multi_sub_dose state", () => {
    const state: TimerStateOut = {
      mode: "count_up",
      as_of: "2026-05-14T12:00:00Z",
      last_dose_at: null,
      count_up: { elapsed_seconds: null },
    };
    expect(windowProgress(state)).toEqual({
      used: 0,
      total: 0,
      remaining: 0,
      nextAvailableAt: null,
    });
  });
});
