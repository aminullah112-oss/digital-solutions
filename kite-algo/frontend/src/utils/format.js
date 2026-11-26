// Small display helpers shared by the tabs. Indian number grouping (1,00,000).

// "2026-11-25" -> "25 Nov 2026". Parsed by hand so time zones can't shift the day.
export function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// 3122.357 -> "3,122.36"
export function formatPrice(n) {
  return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// 1234567.8 -> "₹12,34,568"
export function formatMoney(n) {
  return `${n < 0 ? "-" : ""}₹${Math.round(Math.abs(n)).toLocaleString("en-IN")}`;
}

// 1250000 -> "₹12.5L", 25000000 -> "₹2.50Cr" (for chart axes)
export function formatCompact(n) {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  return `${sign}₹${Math.round(abs).toLocaleString("en-IN")}`;
}

// 4.5 -> "+4.50%", -3 -> "-3.00%", null -> "n/a"
export function formatPct(n, digits = 2) {
  if (n === null || n === undefined) return "n/a";
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

// CSS class for a signed number: green above zero, red below.
export function signClass(n) {
  if (n === null || n === undefined || n === 0) return "";
  return n > 0 ? "pos" : "neg";
}
