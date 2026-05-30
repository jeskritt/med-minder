import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { downloadDoseHistoryCsv } from "@/lib/adherence";

function mockBrowserDownload() {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    blob: async () => new Blob(["csv"]),
  }));
  vi.stubGlobal("fetch", fetchMock);
  globalThis.URL.createObjectURL = vi.fn(() => "blob:fake");
  globalThis.URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  return fetchMock;
}

function calledPath(fetchMock: ReturnType<typeof vi.fn>): string {
  const url = fetchMock.mock.calls[0][0] as string;
  // Strip any configured VITE_API_BASE_URL origin so the assertion is
  // about the path + query the helper builds.
  return url.replace(/^https?:\/\/[^/]+/, "");
}

describe("downloadDoseHistoryCsv", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests the full history when no dates are given", async () => {
    const fetchMock = mockBrowserDownload();
    await downloadDoseHistoryCsv();
    expect(calledPath(fetchMock)).toBe("/api/v1/adherence/export.csv");
  });

  it("appends from and to query params when provided", async () => {
    const fetchMock = mockBrowserDownload();
    await downloadDoseHistoryCsv({ from: "2026-05-01", to: "2026-05-31" });
    expect(calledPath(fetchMock)).toBe(
      "/api/v1/adherence/export.csv?from=2026-05-01&to=2026-05-31",
    );
  });

  it("appends only the provided bound", async () => {
    const fetchMock = mockBrowserDownload();
    await downloadDoseHistoryCsv({ from: "2026-05-01" });
    expect(calledPath(fetchMock)).toBe(
      "/api/v1/adherence/export.csv?from=2026-05-01",
    );
  });

  it("throws when the response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false })),
    );
    await expect(downloadDoseHistoryCsv()).rejects.toThrow(/could not export/i);
  });
});
