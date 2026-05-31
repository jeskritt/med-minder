// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from "vitest";
import { csrfMiddleware } from "@/lib/api";

/**
 * The CSRF request middleware (ADR-0019) echoes the non-HttpOnly `mm_csrf`
 * cookie into the `X-CSRF-Token` header on unsafe requests only.
 */
async function runOnRequest(request: Request): Promise<Request> {
  // openapi-fetch passes a rich options object; the middleware only reads
  // `request`, so a minimal shim is sufficient for a unit test.
  const result = await csrfMiddleware.onRequest!({
    request,
  } as unknown as Parameters<NonNullable<typeof csrfMiddleware.onRequest>>[0]);
  return (result as Request | undefined) ?? request;
}

describe("csrf request middleware", () => {
  beforeEach(() => {
    Object.defineProperty(document, "cookie", {
      writable: true,
      configurable: true,
      value: "mm_csrf=tok-12345",
    });
  });

  it("attaches X-CSRF-Token on a POST", async () => {
    const req = new Request("http://testserver/me", { method: "POST" });
    await runOnRequest(req);
    expect(req.headers.get("X-CSRF-Token")).toBe("tok-12345");
  });

  it("does not attach the header on a GET", async () => {
    const req = new Request("http://testserver/me", { method: "GET" });
    await runOnRequest(req);
    expect(req.headers.get("X-CSRF-Token")).toBeNull();
  });

  it("does nothing when the cookie is absent", async () => {
    Object.defineProperty(document, "cookie", {
      writable: true,
      configurable: true,
      value: "",
    });
    const req = new Request("http://testserver/me", { method: "DELETE" });
    await runOnRequest(req);
    expect(req.headers.get("X-CSRF-Token")).toBeNull();
  });
});
