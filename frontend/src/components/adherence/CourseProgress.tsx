/**
 * Course progress for fixed-course medications (US2).
 *
 * "N of M doses" with a token-driven progress bar and a completion badge once
 * the course is done. Display-only — completion has no side effects (FR-008).
 */

import { CheckCircle2 } from "lucide-react";
import type { CourseProgress as CourseProgressData } from "@/lib/adherence";

export interface CourseProgressProps {
  course: CourseProgressData;
}

export function CourseProgress({ course }: CourseProgressProps) {
  const pct = Math.min(100, Math.round((course.taken / course.total) * 100));

  return (
    <section
      aria-label="Course progress"
      className="rounded-xl border border-border bg-secondary/40 p-4"
    >
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Course progress
        </h3>
        <p className="text-sm tabular-nums text-muted-foreground">
          <span className="font-semibold text-foreground">{course.taken}</span>{" "}
          of {course.total} doses
        </p>
      </div>

      <div
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={course.total}
        aria-valuenow={course.taken}
      >
        <div
          className="h-full rounded-full bg-success transition-[width] duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>

      {course.complete && (
        <p className="mm-chip mt-3 bg-success/15 text-success">
          <CheckCircle2 className="size-3.5" aria-hidden="true" />
          Course complete
        </p>
      )}
    </section>
  );
}
