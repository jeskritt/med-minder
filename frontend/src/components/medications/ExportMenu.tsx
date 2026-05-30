/**
 * Export menu for dose history (Phase 9 + date-range filter).
 *
 * A small disclosure beside Add/Print: the trigger toggles a popover with two
 * optional date inputs (From / To, blank = full history) and a Download button.
 * Soft-Apothecary styling via the shared mm-* classes.
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { downloadDoseHistoryCsv } from "@/lib/adherence";

export function ExportMenu() {
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const exportMutation = useMutation({
    mutationFn: () =>
      downloadDoseHistoryCsv({ from: from || undefined, to: to || undefined }),
    onSuccess: () => setOpen(false),
  });

  const invalidRange = from !== "" && to !== "" && to < from;

  return (
    <div className="relative print:hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="mm-btn mm-btn-secondary"
      >
        <Download className="size-4" />
        Export
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Export dose history"
          className="mm-card absolute right-0 z-10 mt-2 w-72 space-y-3 p-4"
        >
          <p className="text-sm text-muted-foreground">
            Export your dose history as CSV. Leave the dates blank for
            everything.
          </p>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-muted-foreground">
              From
              <input
                type="date"
                value={from}
                max={to || undefined}
                onChange={(e) => setFrom(e.target.value)}
                className="mm-input mt-1"
              />
            </label>
            <label className="text-xs font-medium text-muted-foreground">
              To
              <input
                type="date"
                value={to}
                min={from || undefined}
                onChange={(e) => setTo(e.target.value)}
                className="mm-input mt-1"
              />
            </label>
          </div>
          {invalidRange && (
            <p role="alert" className="text-xs text-destructive">
              The “To” date can’t be before “From”.
            </p>
          )}
          {exportMutation.isError && (
            <p role="alert" className="text-xs text-destructive">
              Could not export your dose history. Please try again.
            </p>
          )}
          <button
            type="button"
            onClick={() => exportMutation.mutate()}
            disabled={invalidRange || exportMutation.isPending}
            className="mm-btn mm-btn-primary mm-btn-block"
          >
            <Download className="size-4" />
            {exportMutation.isPending ? "Exporting…" : "Download CSV"}
          </button>
        </div>
      )}
    </div>
  );
}
