import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * FR-006 / SC-004: the service worker precaches ONLY the static app shell and
 * never caches `/api` (no PHI in Cache Storage). These are source-level
 * invariants so the guarantee is enforced without a build step. Paths resolve
 * from the package root (vitest runs with cwd = frontend/).
 */
const sw = readFileSync(resolve(process.cwd(), "src/sw.ts"), "utf8");
const viteConfig = readFileSync(
  resolve(process.cwd(), "vite.config.ts"),
  "utf8",
);

describe("service worker caching policy (FR-006 / SC-004)", () => {
  it("precaches only the build manifest", () => {
    expect(sw).toContain("precacheAndRoute(self.__WB_MANIFEST)");
  });

  it("excludes /api from the navigation fallback", () => {
    expect(sw).toContain("denylist");
    expect(sw).toMatch(/\/\^\\\/api/); // the /^\/api\// denylist pattern
  });

  it("registers no runtime caching strategy (nothing dynamic is cached)", () => {
    expect(sw).not.toMatch(/CacheFirst|StaleWhileRevalidate|NetworkFirst/);
  });

  it("only globs static shell assets for precaching — no /api, no json", () => {
    const glob = viteConfig.match(/globPatterns:\s*\[([^\]]*)\]/);
    expect(glob).not.toBeNull();
    const patterns = glob?.[1] ?? "";
    expect(patterns).not.toContain("api");
    expect(patterns).not.toContain("json");
  });
});
