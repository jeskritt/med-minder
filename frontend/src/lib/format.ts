/**
 * Display helpers shared across views.
 */

/**
 * Trim trailing zeros from a decimal string the API returns (e.g.
 * `"200.000"` → `"200"`, `"2.500"` → `"2.5"`). Leaves non-numeric
 * input untouched.
 */
export function formatQuantity(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  // toString drops trailing zeros and the trailing dot.
  return n.toString();
}
